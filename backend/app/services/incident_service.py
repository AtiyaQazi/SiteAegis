from sqlalchemy.orm import Session

from app.models.incident import Incident
from app.models.safety_event import SafetyEvent


INCIDENT_RISK_THRESHOLD = 70


def should_create_incident(event: SafetyEvent) -> bool:
    """
    Decide whether a safety event is serious enough
    to become an incident.
    """

    severity = (event.severity or "").lower()

    if severity in {"high", "critical"}:
        return True

    if event.risk_score >= INCIDENT_RISK_THRESHOLD:
        return True

    return False


def get_incident_by_event(
    db: Session,
    event_id: int,
) -> Incident | None:
    """
    Find an existing incident for a safety event.
    Prevents duplicate incidents.
    """

    return (
        db.query(Incident)
        .filter(Incident.event_id == event_id)
        .first()
    )


def create_incident_from_event(
    db: Session,
    event: SafetyEvent,
) -> Incident | None:
    """
    Automatically create an Incident from a high-risk
    SafetyEvent.

    Returns:
        Incident if created.
        Existing Incident if already created.
        None if the event does not meet the incident threshold.
    """

    if not should_create_incident(event):
        print(
            f"[INCIDENT SERVICE] Event #{event.id} "
            f"does not require an incident."
        )
        return None

    existing_incident = get_incident_by_event(
        db,
        event.id,
    )

    if existing_incident is not None:
        print(
            f"[INCIDENT SERVICE] Incident already exists "
            f"for event #{event.id}: "
            f"incident #{existing_incident.id}"
        )

        return existing_incident

    incident = Incident(
        event_id=event.id,
        camera_id=event.camera_id,
        zone_id=event.zone_id,
        title=event.title,
        description=event.description,
        incident_type=event.event_type,
        severity=event.severity,
        risk_score=event.risk_score,
        status="open",
    )

    db.add(incident)
    db.commit()
    db.refresh(incident)

    print(
        f"[INCIDENT SERVICE] Created incident "
        f"#{incident.id} from safety event #{event.id}"
    )

    return incident