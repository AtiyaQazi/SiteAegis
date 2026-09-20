from io import BytesIO

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from PIL import Image
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.zone import Zone
from app.schemas.zone import (
    ZoneCreate,
    ZoneResponse,
    ZoneUpdate,
)
from app.services.vision_service import (
    detect_persons_from_image,
)
from app.services.zone_service import (
    create_restricted_zone_event,
    detect_persons_in_zone,
    update_zone_presence,
)


router = APIRouter(
    prefix="/zones",
    tags=["Zones"],
)


@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_zone(
    zone_data: ZoneCreate,
    db: Session = Depends(get_db),
):
    zone = Zone(
        name=zone_data.name,
        description=zone_data.description,
        location=zone_data.location,
        risk_level=zone_data.risk_level,
        polygon=zone_data.polygon,
    )

    db.add(zone)
    db.commit()
    db.refresh(zone)

    return zone


@router.get(
    "",
    response_model=list[ZoneResponse],
)
def get_zones(
    db: Session = Depends(get_db),
):
    return (
        db.query(Zone)
        .order_by(Zone.id.desc())
        .all()
    )


@router.post(
    "/{zone_id}/detect-entry",
)
async def detect_zone_entry(
    zone_id: int,
    file: UploadFile = File(...),
    camera_id: int | None = None,
    db: Session = Depends(get_db),
):
    """
    Analyze an uploaded image for people entering a
    restricted zone.

    Detection flow:

        image
          ↓
        YOLO person detection
          ↓
        feet point
          ↓
        polygon check
          ↓
        persistent zone presence
          ↓
        NEW ENTRY?
          ↓
        SafetyEvent
          ↓
        Incident
    """

    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    if not zone.polygon:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Zone does not have a polygon configured"
            ),
        )

    if (
        not file.content_type
        or not file.content_type.startswith("image/")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be an image",
        )

    try:
        contents = await file.read()

        if not contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image is empty",
            )

        image = Image.open(
            BytesIO(contents)
        ).convert("RGB")

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to read image: {exc}",
        )

    image_width, image_height = image.size

    # --------------------------------------------------------
    # YOLO PERSON DETECTION
    # --------------------------------------------------------

    detections = detect_persons_from_image(
        image,
        minimum_confidence=0.25,
    )

    # --------------------------------------------------------
    # RESTRICTED-ZONE PERSON DETECTION
    # --------------------------------------------------------

    persons_in_zone = detect_persons_in_zone(
        zone=zone,
        detections=detections,
        image_width=image_width,
        image_height=image_height,
    )

    # --------------------------------------------------------
    # UPDATE PERSISTENT ZONE PRESENCE
    # --------------------------------------------------------
    #
    # update_zone_presence() maintains the state machine:
    #
    # OUTSIDE -> INSIDE = new entry
    # INSIDE -> INSIDE  = no new entry
    # INSIDE -> OUTSIDE = exit/reset
    # OUTSIDE -> OUTSIDE = no event
    #
    # IMPORTANT:
    # The service expects zone_id, not zone.
    # --------------------------------------------------------

    is_new_entry = update_zone_presence(
        db=db,
        zone_id=zone.id,
        camera_id=camera_id,
        persons_in_zone=persons_in_zone,
    )

    events_created = []

    # --------------------------------------------------------
    # CREATE ONLY ONE EVENT FOR A NEW ENTRY
    # --------------------------------------------------------

    if is_new_entry and persons_in_zone:

        # One zone-entry event is generated for the first
        # detected person. Additional persons in the same
        # image do not create duplicate zone events.
        person = persons_in_zone[0]

        event = create_restricted_zone_event(
            db=db,
            zone=zone,
            person_detection=person,
            camera_id=camera_id,
        )

        if event is not None:

            events_created.append(
                {
                    "id": event.id,
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "title": event.title,
                    "description": event.description,
                    "confidence": event.confidence,
                    "detected_object": event.detected_object,
                    "risk_score": event.risk_score,
                    "status": event.status,
                    "zone_id": event.zone_id,
                    "camera_id": event.camera_id,
                    "occurred_at": event.occurred_at,
                }
            )

    # --------------------------------------------------------
    # DATABASE COMMIT
    # --------------------------------------------------------

    db.commit()

    return {
        "zone_id": zone.id,
        "zone_name": zone.name,
        "risk_level": zone.risk_level,
        "image": {
            "filename": file.filename,
            "content_type": file.content_type,
            "width": image_width,
            "height": image_height,
        },
        "detection": {
            "total_persons": len(detections),
            "persons_inside_zone": len(persons_in_zone),
            "restricted_zone_entry_detected": (
                len(persons_in_zone) > 0
            ),
            "new_entry": is_new_entry,
        },
        "persons": persons_in_zone,
        "events_created": events_created,
    }


@router.get(
    "/{zone_id}",
    response_model=ZoneResponse,
)
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    return zone


@router.put(
    "/{zone_id}",
    response_model=ZoneResponse,
)
def update_zone(
    zone_id: int,
    zone_data: ZoneUpdate,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    update_data = zone_data.model_dump(
        exclude_unset=True,
    )

    for field, value in update_data.items():
        setattr(
            zone,
            field,
            value,
        )

    db.commit()
    db.refresh(zone)

    return zone


@router.delete(
    "/{zone_id}",
)
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    db.delete(zone)
    db.commit()

    return {
        "message": "Zone deleted successfully",
        "zone_id": zone_id,
    }