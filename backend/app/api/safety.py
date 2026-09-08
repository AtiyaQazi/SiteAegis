from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.models.safety_event import SafetyEvent
from app.models.zone import Zone
from app.schemas.safety_event import (
    SafetyEventCreate,
    SafetyEventResponse,
    SafetyEventUpdate,
)
from app.services.incident_service import (
    create_incident_from_event,
)


router = APIRouter(
    prefix="/safety",
    tags=["Safety Events"],
)


@router.post(
    "/events",
    response_model=SafetyEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_safety_event(
    event_data: SafetyEventCreate,
    db: Session = Depends(get_db),
):
    if event_data.camera_id is not None:
        camera = (
            db.query(Camera)
            .filter(Camera.id == event_data.camera_id)
            .first()
        )

        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Camera not found",
            )

    if event_data.zone_id is not None:
        zone = (
            db.query(Zone)
            .filter(Zone.id == event_data.zone_id)
            .first()
        )

        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

    event = SafetyEvent(
        camera_id=event_data.camera_id,
        zone_id=event_data.zone_id,
        event_type=event_data.event_type,
        severity=event_data.severity,
        title=event_data.title,
        description=event_data.description,
        confidence=event_data.confidence,
        detected_object=event_data.detected_object,
        risk_score=event_data.risk_score,
        status=event_data.status,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    # Automatically create an incident when the
    # safety event meets the configured risk threshold.
    create_incident_from_event(
        db=db,
        event=event,
    )

    return event


@router.get(
    "/events",
    response_model=list[SafetyEventResponse],
)
def get_safety_events(
    db: Session = Depends(get_db),
):
    return (
        db.query(SafetyEvent)
        .order_by(SafetyEvent.id.desc())
        .all()
    )


@router.get(
    "/events/{event_id}",
    response_model=SafetyEventResponse,
)
def get_safety_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = (
        db.query(SafetyEvent)
        .filter(SafetyEvent.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    return event


@router.put(
    "/events/{event_id}",
    response_model=SafetyEventResponse,
)
def update_safety_event(
    event_id: int,
    event_data: SafetyEventUpdate,
    db: Session = Depends(get_db),
):
    event = (
        db.query(SafetyEvent)
        .filter(SafetyEvent.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    if event_data.camera_id is not None:
        camera = (
            db.query(Camera)
            .filter(Camera.id == event_data.camera_id)
            .first()
        )

        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Camera not found",
            )

    if event_data.zone_id is not None:
        zone = (
            db.query(Zone)
            .filter(Zone.id == event_data.zone_id)
            .first()
        )

        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

    update_data = event_data.model_dump(
        exclude_unset=True,
    )

    for field, value in update_data.items():
        setattr(event, field, value)

    db.commit()
    db.refresh(event)

    return event


@router.delete(
    "/events/{event_id}",
)
def delete_safety_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    event = (
        db.query(SafetyEvent)
        .filter(SafetyEvent.id == event_id)
        .first()
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    db.delete(event)
    db.commit()

    return {
        "message": "Safety event deleted successfully",
        "event_id": event_id,
    }