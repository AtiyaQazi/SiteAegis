from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.models.incident import Incident
from app.models.safety_event import SafetyEvent
from app.models.zone import Zone
from app.schemas.incident import (
    IncidentCreate,
    IncidentResponse,
    IncidentUpdate,
)


router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"],
)


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_incident(
    incident_data: IncidentCreate,
    db: Session = Depends(get_db),
):
    if incident_data.event_id is not None:
        event = (
            db.query(SafetyEvent)
            .filter(SafetyEvent.id == incident_data.event_id)
            .first()
        )

        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Safety event not found",
            )

    if incident_data.camera_id is not None:
        camera = (
            db.query(Camera)
            .filter(Camera.id == incident_data.camera_id)
            .first()
        )

        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Camera not found",
            )

    if incident_data.zone_id is not None:
        zone = (
            db.query(Zone)
            .filter(Zone.id == incident_data.zone_id)
            .first()
        )

        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

    incident = Incident(
        event_id=incident_data.event_id,
        camera_id=incident_data.camera_id,
        zone_id=incident_data.zone_id,
        title=incident_data.title,
        description=incident_data.description,
        incident_type=incident_data.incident_type,
        severity=incident_data.severity,
        risk_score=incident_data.risk_score,
        status=incident_data.status,
        resolution_notes=incident_data.resolution_notes,
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    return incident


@router.get(
    "",
    response_model=list[IncidentResponse],
)
def get_incidents(
    db: Session = Depends(get_db),
):
    return (
        db.query(Incident)
        .order_by(Incident.id.desc())
        .all()
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def get_incident(
    incident_id: int,
    db: Session = Depends(get_db),
):
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    return incident


@router.put(
    "/{incident_id}",
    response_model=IncidentResponse,
)
def update_incident(
    incident_id: int,
    incident_data: IncidentUpdate,
    db: Session = Depends(get_db),
):
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    if incident_data.event_id is not None:
        event = (
            db.query(SafetyEvent)
            .filter(SafetyEvent.id == incident_data.event_id)
            .first()
        )

        if event is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Safety event not found",
            )

    if incident_data.camera_id is not None:
        camera = (
            db.query(Camera)
            .filter(Camera.id == incident_data.camera_id)
            .first()
        )

        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Camera not found",
            )

    if incident_data.zone_id is not None:
        zone = (
            db.query(Zone)
            .filter(Zone.id == incident_data.zone_id)
            .first()
        )

        if zone is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Zone not found",
            )

    update_data = incident_data.model_dump(
        exclude_unset=True,
    )

    for field, value in update_data.items():
        setattr(incident, field, value)

    if (
        "status" in update_data
        and update_data["status"] == "resolved"
        and incident.resolved_at is None
    ):
        from datetime import datetime, timezone

        incident.resolved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(incident)

    return incident


@router.delete(
    "/{incident_id}",
)
def delete_incident(
    incident_id: int,
    db: Session = Depends(get_db),
):
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Incident not found",
        )

    db.delete(incident)
    db.commit()

    return {
        "message": "Incident deleted successfully",
        "incident_id": incident_id,
    }