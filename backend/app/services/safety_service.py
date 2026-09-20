from sqlalchemy.orm import Session

from app.models.camera import Camera
from app.models.safety_event import SafetyEvent
from app.models.zone import Zone
from app.schemas.safety_event import SafetyEventCreate, SafetyEventUpdate
from app.services.incident_service import create_incident_from_event


VALID_SEVERITIES = {
    "low",
    "medium",
    "high",
    "critical",
}

VALID_STATUSES = {
    "active",
    "resolved",
    "dismissed",
}


def validate_camera(
    db: Session,
    camera_id: int | None,
) -> None:
    """
    Validate that the referenced camera exists.
    """

    if camera_id is None:
        return

    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise ValueError("Camera not found")


def validate_zone(
    db: Session,
    zone_id: int | None,
) -> None:
    """
    Validate that the referenced zone exists.
    """

    if zone_id is None:
        return

    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise ValueError("Zone not found")


def normalize_severity(
    severity: str | None,
) -> str:
    """
    Normalize and validate event severity.
    """

    normalized = (
        severity or "low"
    ).strip().lower()

    if normalized not in VALID_SEVERITIES:
        raise ValueError(
            f"Invalid severity '{severity}'. "
            f"Allowed values: {', '.join(sorted(VALID_SEVERITIES))}"
        )

    return normalized


def normalize_status(
    status: str | None,
) -> str:
    """
    Normalize and validate event status.
    """

    normalized = (
        status or "active"
    ).strip().lower()

    if normalized not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. "
            f"Allowed values: {', '.join(sorted(VALID_STATUSES))}"
        )

    return normalized


def normalize_confidence(
    confidence: float | None,
) -> float | None:
    """
    Validate AI confidence score.

    Confidence must be between 0 and 1.
    """

    if confidence is None:
        return None

    if not 0.0 <= confidence <= 1.0:
        raise ValueError(
            "Confidence must be between 0.0 and 1.0"
        )

    return float(confidence)


def normalize_risk_score(
    risk_score: int | None,
) -> int:
    """
    Normalize AI-generated risk score.

    Risk score must be between 0 and 100.
    """

    if risk_score is None:
        return 0

    if not 0 <= risk_score <= 100:
        raise ValueError(
            "Risk score must be between 0 and 100"
        )

    return int(risk_score)


def create_safety_event(
    db: Session,
    event_data: SafetyEventCreate,
) -> SafetyEvent:
    """
    Create a SafetyEvent and automatically create
    an Incident when the event is high risk.
    """

    validate_camera(
        db,
        event_data.camera_id,
    )

    validate_zone(
        db,
        event_data.zone_id,
    )

    severity = normalize_severity(
        event_data.severity,
    )

    status = normalize_status(
        event_data.status,
    )

    confidence = normalize_confidence(
        event_data.confidence,
    )

    risk_score = normalize_risk_score(
        event_data.risk_score,
    )

    event = SafetyEvent(
        camera_id=event_data.camera_id,
        zone_id=event_data.zone_id,
        event_type=event_data.event_type.strip(),
        severity=severity,
        title=event_data.title.strip(),
        description=event_data.description,
        confidence=confidence,
        detected_object=event_data.detected_object,
        risk_score=risk_score,
        status=status,
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    # Automatically create an incident when required.
    create_incident_from_event(
        db=db,
        event=event,
    )

    return event


def get_safety_event(
    db: Session,
    event_id: int,
) -> SafetyEvent | None:
    """
    Get a single SafetyEvent by ID.
    """

    return (
        db.query(SafetyEvent)
        .filter(SafetyEvent.id == event_id)
        .first()
    )


def get_safety_events(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    camera_id: int | None = None,
    zone_id: int | None = None,
    limit: int = 100,
) -> list[SafetyEvent]:
    """
    Return safety events ordered by newest first.

    Optional filters:
    - status
    - severity
    - event_type
    - camera_id
    - zone_id

    Results are limited to the requested number of events.
    """

    query = db.query(SafetyEvent)

    if status is not None:
        normalized_status = normalize_status(status)

        query = query.filter(
            SafetyEvent.status == normalized_status
        )

    if severity is not None:
        normalized_severity = normalize_severity(severity)

        query = query.filter(
            SafetyEvent.severity == normalized_severity
        )

    if event_type is not None:
        normalized_event_type = event_type.strip()

        if normalized_event_type:
            query = query.filter(
                SafetyEvent.event_type == normalized_event_type
            )

    if camera_id is not None:
        query = query.filter(
            SafetyEvent.camera_id == camera_id
        )

    if zone_id is not None:
        query = query.filter(
            SafetyEvent.zone_id == zone_id
        )

    return (
        query
        .order_by(SafetyEvent.id.desc())
        .limit(limit)
        .all()
    )


def update_safety_event(
    db: Session,
    event_id: int,
    event_data: SafetyEventUpdate | dict,
) -> SafetyEvent | None:
    """
    Update an existing SafetyEvent.

    Only explicitly supplied fields are modified.
    """

    event = get_safety_event(
        db,
        event_id,
    )

    if event is None:
        return None

    if isinstance(event_data, dict):
        update_data = event_data
    else:
        update_data = event_data.model_dump(
            exclude_unset=True,
        )

    if "camera_id" in update_data:
        validate_camera(
            db,
            update_data["camera_id"],
        )

    if "zone_id" in update_data:
        validate_zone(
            db,
            update_data["zone_id"],
        )

    if "severity" in update_data:
        update_data["severity"] = normalize_severity(
            update_data["severity"],
        )

    if "status" in update_data:
        update_data["status"] = normalize_status(
            update_data["status"],
        )

    if "confidence" in update_data:
        update_data["confidence"] = normalize_confidence(
            update_data["confidence"],
        )

    if "risk_score" in update_data:
        update_data["risk_score"] = normalize_risk_score(
            update_data["risk_score"],
        )

    if "event_type" in update_data:
        update_data["event_type"] = (
            update_data["event_type"].strip()
        )

    if "title" in update_data:
        update_data["title"] = (
            update_data["title"].strip()
        )

    for field, value in update_data.items():
        setattr(
            event,
            field,
            value,
        )

    db.commit()
    db.refresh(event)

    return event


def delete_safety_event(
    db: Session,
    event_id: int,
) -> SafetyEvent | None:
    """
    Delete a SafetyEvent.

    Returns the deleted event when successful,
    otherwise None.
    """

    event = get_safety_event(
        db,
        event_id,
    )

    if event is None:
        return None

    db.delete(event)
    db.commit()

    return event