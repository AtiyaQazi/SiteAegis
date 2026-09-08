from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.monitoring_event import MonitoringEvent


def create_alert_from_event(
    db: Session,
    event: MonitoringEvent,
) -> Alert:
    """
    Create a user-facing alert from a monitoring event.
    """

    alert = Alert(
        site_id=event.site_id,
        event_id=event.id,
        alert_type=event.event_type,
        severity=event.severity,
        title=event.title,
        message=event.description,
        is_read=False,
    )

    db.add(alert)

    return alert


def create_alerts_from_events(
    db: Session,
    events: list[MonitoringEvent],
) -> list[Alert]:
    """
    Convert multiple monitoring events into alerts.
    """

    alerts: list[Alert] = []

    for event in events:
        alert = create_alert_from_event(
            db=db,
            event=event,
        )

        alerts.append(alert)

    return alerts