from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.monitoring_event import MonitoringEvent


def create_alert_from_event(
    db: Session,
    event: MonitoringEvent,
) -> Alert:
    """
    Create a user-facing alert from a monitoring event.

    The monitoring event must already have a database ID
    before the alert is created so the foreign-key
    relationship is stored correctly.
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

    MonitoringEvent objects are flushed first so SQLAlchemy
    assigns their database IDs before those IDs are used as
    Alert.event_id foreign keys.
    """

    alerts: list[Alert] = []

    if not events:
        return alerts

    # --------------------------------------------------
    # ENSURE MONITORING EVENT IDS EXIST
    # --------------------------------------------------
    #
    # detect_scan_changes() adds MonitoringEvent objects
    # to the current SQLAlchemy session. Their primary keys
    # may still be None until the session is flushed.
    #
    # Alert.event_id depends on those IDs, so flush the
    # pending monitoring events before creating alerts.
    # --------------------------------------------------

    db.flush()

    # --------------------------------------------------
    # CREATE ALERTS
    # --------------------------------------------------

    for event in events:
        alert = create_alert_from_event(
            db=db,
            event=event,
        )

        alerts.append(alert)

    return alerts
