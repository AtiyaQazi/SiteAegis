from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from PIL import Image
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.safety_event import SafetyEventCreate
from app.services.crowding_service import (
    DEFAULT_CROWD_THRESHOLD,
    process_crowding,
)
from app.services.fall_detection_service import (
    DEFAULT_FALL_ASPECT_RATIO,
    DEFAULT_MIN_FALL_WIDTH,
    process_fall_detection,
)
from app.services.proximity_service import (
    DEFAULT_PROXIMITY_THRESHOLD,
    process_worker_machine_proximity,
)
from app.services.unsafe_movement_service import (
    DEFAULT_CRITICAL_MOVEMENT_THRESHOLD,
    DEFAULT_MOVEMENT_THRESHOLD,
    process_unsafe_movement,
)
from app.services.vision_service import (
    PERSON_MODEL,
    detect_objects_from_image,
)
from app.services.safety_service import (
    create_safety_event,
    get_safety_event,
    get_safety_events,
    update_safety_event,
    delete_safety_event,
)


router = APIRouter(
    prefix="/safety",
    tags=["Safety"],
)


# ============================================================
# IMAGE HELPERS
# ============================================================


def validate_image_type(
    file: UploadFile,
) -> None:
    if not file.content_type:
        raise HTTPException(
            status_code=400,
            detail="Image content type is required.",
        )

    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Only image files are supported.",
        )


async def read_image(
    file: UploadFile,
) -> Image.Image:
    validate_image_type(file)

    try:
        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty.",
            )

        from io import BytesIO

        image = Image.open(
            BytesIO(content)
        ).convert("RGB")

        return image

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Unable to read image: {exc}",
        )


# ============================================================
# BASIC SAFETY EVENT CRUD
# ============================================================


@router.post("")
def create_safety_event_api(
    event_data: SafetyEventCreate,
    db: Session = Depends(get_db),
):
    return create_safety_event(
        db=db,
        event_data=event_data,
    )


@router.get("")
def list_safety_events(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    camera_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    return get_safety_events(
        db=db,
        status=status,
        severity=severity,
        event_type=event_type,
        camera_id=camera_id,
        zone_id=zone_id,
        limit=limit,
    )


@router.get("/events")
def list_safety_events_alias(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    camera_id: Optional[int] = Query(None),
    zone_id: Optional[int] = Query(None),
    limit: int = Query(
        100,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    return get_safety_events(
        db=db,
        status=status,
        severity=severity,
        event_type=event_type,
        camera_id=camera_id,
        zone_id=zone_id,
        limit=limit,
    )


@router.get("/{event_id}")
def get_safety_event_api(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = get_safety_event(
        db=db,
        event_id=event_id,
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Safety event not found.",
        )

    return event


@router.put("/{event_id}")
def update_safety_event_api(
    event_id: int,
    event_data: dict,
    db: Session = Depends(get_db),
):
    event = update_safety_event(
        db=db,
        event_id=event_id,
        update_data=event_data,
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Safety event not found.",
        )

    return event


@router.delete("/{event_id}")
def delete_safety_event_api(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = delete_safety_event(
        db=db,
        event_id=event_id,
    )

    if event is None:
        raise HTTPException(
            status_code=404,
            detail="Safety event not found.",
        )

    return {
        "success": True,
        "event_id": event_id,
    }


# ============================================================
# WORKER-MACHINE PROXIMITY
# ============================================================


@router.post("/proximity/analyze")
async def analyze_proximity_api(
    file: UploadFile = File(...),
    camera_id: Optional[int] = Form(None),
    proximity_threshold: float = Form(
        DEFAULT_PROXIMITY_THRESHOLD
    ),
    db: Session = Depends(get_db),
):
    if proximity_threshold <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "proximity_threshold must "
                "be greater than 0."
            ),
        )

    image = await read_image(file)

    detections = detect_objects_from_image(
        image=image,
        model_path=PERSON_MODEL,
        minimum_confidence=0.20,
    )

    result = process_worker_machine_proximity(
        db=db,
        detections=detections,
        camera_id=camera_id,
        threshold=proximity_threshold,
    )

    proximity_detections = result.get(
        "proximity_detections",
        [],
    )

    safety_events = result.get(
        "safety_events",
        [],
    )

    return {
        "success": True,
        "image": {
            "filename": file.filename,
            "content_type": file.content_type,
            "width": image.width,
            "height": image.height,
        },
        "configuration": {
            "proximity_threshold": proximity_threshold,
            "camera_id": camera_id,
            "model": PERSON_MODEL,
        },
        "detection": {
            "total_objects": len(detections),
            "workers": result.get(
                "worker_count",
                0,
            ),
            "machines": result.get(
                "machine_count",
                0,
            ),
            "proximity_events": len(
                proximity_detections
            ),
            "safety_events_created": len(
                safety_events
            ),
        },
        "detections": proximity_detections,
        "safety_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "risk_score": event.risk_score,
                "status": event.status,
            }
            for event in safety_events
        ],
    }


# ============================================================
# CROWDING DETECTION
# ============================================================


@router.post("/crowding/analyze")
async def analyze_crowding_api(
    file: UploadFile = File(...),
    camera_id: Optional[int] = Form(None),
    crowd_threshold: int = Form(
        DEFAULT_CROWD_THRESHOLD
    ),
    db: Session = Depends(get_db),
):
    if crowd_threshold <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "crowd_threshold must "
                "be greater than 0."
            ),
        )

    image = await read_image(file)

    detections = detect_objects_from_image(
        image=image,
        model_path=PERSON_MODEL,
        minimum_confidence=0.20,
    )

    result = process_crowding(
        db=db,
        detections=detections,
        camera_id=camera_id,
        threshold=crowd_threshold,
    )

    crowding = result.get(
        "crowding",
        {},
    )

    safety_event = result.get(
        "safety_event"
    )

    return {
        "success": True,
        "image": {
            "filename": file.filename,
            "content_type": file.content_type,
            "width": image.width,
            "height": image.height,
        },
        "configuration": {
            "crowd_threshold": crowd_threshold,
            "camera_id": camera_id,
            "model": PERSON_MODEL,
        },
        "detection": {
            "person_count": crowding.get(
                "person_count",
                0,
            ),
            "crowding_detected": crowding.get(
                "crowding_detected",
                False,
            ),
            "excess_persons": crowding.get(
                "excess_persons",
                0,
            ),
            "risk_level": crowding.get(
                "risk_level",
                "low",
            ),
            "risk_score": crowding.get(
                "risk_score",
                0,
            ),
            "safety_event_created": (
                safety_event is not None
            ),
        },
        "detections": crowding.get(
            "persons",
            [],
        ),
        "safety_events": (
            [
                {
                    "id": safety_event.id,
                    "event_type": safety_event.event_type,
                    "severity": safety_event.severity,
                    "risk_score": safety_event.risk_score,
                    "status": safety_event.status,
                }
            ]
            if safety_event is not None
            else []
        ),
    }


# ============================================================
# FALL DETECTION
# ============================================================


@router.post("/fall/analyze")
async def analyze_fall_api(
    file: UploadFile = File(...),
    camera_id: Optional[int] = Form(None),
    fall_aspect_ratio: float = Form(
        DEFAULT_FALL_ASPECT_RATIO
    ),
    min_fall_width: float = Form(
        DEFAULT_MIN_FALL_WIDTH
    ),
    db: Session = Depends(get_db),
):
    if fall_aspect_ratio <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "fall_aspect_ratio must "
                "be greater than 0."
            ),
        )

    if min_fall_width <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "min_fall_width must "
                "be greater than 0."
            ),
        )

    image = await read_image(file)

    detections = detect_objects_from_image(
        image=image,
        model_path=PERSON_MODEL,
        minimum_confidence=0.20,
    )

    result = process_fall_detection(
        db=db,
        detections=detections,
        camera_id=camera_id,
        fall_aspect_ratio=fall_aspect_ratio,
        min_fall_width=min_fall_width,
    )

    return {
        "success": True,
        "image": {
            "filename": file.filename,
            "content_type": file.content_type,
            "width": image.width,
            "height": image.height,
        },
        "configuration": {
            "fall_aspect_ratio": fall_aspect_ratio,
            "minimum_fall_width": min_fall_width,
            "camera_id": camera_id,
            "model": PERSON_MODEL,
        },
        "detection": {
            "total_persons": result.get(
                "total_persons",
                0,
            ),
            "fall_candidates": result.get(
                "fall_candidates",
                0,
            ),
            "safety_events_created": result.get(
                "events_created",
                0,
            ),
        },
        "detections": result.get(
            "detections",
            [],
        ),
        "safety_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "risk_score": event.risk_score,
                "status": event.status,
            }
            for event in result.get(
                "safety_events",
                [],
            )
        ],
    }


# ============================================================
# UNSAFE MOVEMENT DETECTION
# ============================================================


@router.post("/unsafe-movement/analyze")
async def analyze_unsafe_movement_api(
    previous_file: UploadFile = File(...),
    current_file: UploadFile = File(...),
    camera_id: Optional[int] = Form(None),
    movement_threshold: float = Form(
        DEFAULT_MOVEMENT_THRESHOLD
    ),
    critical_movement_threshold: float = Form(
        DEFAULT_CRITICAL_MOVEMENT_THRESHOLD
    ),
    db: Session = Depends(get_db),
):
    if movement_threshold <= 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "movement_threshold must "
                "be greater than 0."
            ),
        )

    if (
        critical_movement_threshold
        <= movement_threshold
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "critical_movement_threshold "
                "must be greater than "
                "movement_threshold."
            ),
        )

    previous_image = await read_image(
        previous_file
    )

    current_image = await read_image(
        current_file
    )

    previous_detections = (
        detect_objects_from_image(
            image=previous_image,
            model_path=PERSON_MODEL,
            minimum_confidence=0.20,
        )
    )

    current_detections = (
        detect_objects_from_image(
            image=current_image,
            model_path=PERSON_MODEL,
            minimum_confidence=0.20,
        )
    )

    result = process_unsafe_movement(
        db=db,
        previous_detections=previous_detections,
        current_detections=current_detections,
        camera_id=camera_id,
        movement_threshold=movement_threshold,
        critical_movement_threshold=(
            critical_movement_threshold
        ),
    )

    return {
        "success": True,
        "frames": {
            "previous": {
                "filename": previous_file.filename,
                "content_type": (
                    previous_file.content_type
                ),
                "width": previous_image.width,
                "height": previous_image.height,
            },
            "current": {
                "filename": current_file.filename,
                "content_type": (
                    current_file.content_type
                ),
                "width": current_image.width,
                "height": current_image.height,
            },
        },
        "configuration": {
            "movement_threshold": (
                movement_threshold
            ),
            "critical_movement_threshold": (
                critical_movement_threshold
            ),
            "camera_id": camera_id,
            "model": PERSON_MODEL,
        },
        "detection": {
            "previous_persons": result.get(
                "previous_persons",
                0,
            ),
            "current_persons": result.get(
                "current_persons",
                0,
            ),
            "matched_persons": result.get(
                "matched_persons",
                0,
            ),
            "unsafe_movement_detected": (
                result.get(
                    "unsafe_movement_detected",
                    False,
                )
            ),
            "unsafe_movement_count": (
                result.get(
                    "unsafe_movement_count",
                    0,
                )
            ),
            "events_created": result.get(
                "events_created",
                0,
            ),
        },
        "detections": result.get(
            "detections",
            [],
        ),
        "safety_events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "risk_score": event.risk_score,
                "status": event.status,
            }
            for event in result.get(
                "safety_events",
                [],
            )
        ],
    }