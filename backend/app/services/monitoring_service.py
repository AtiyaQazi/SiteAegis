import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Site, Scan
from app.services.site_service import run_site_scan
from app.services.monitoring_events import detect_scan_changes
from app.services.alert_service import create_alerts_from_events
from app.websocket.manager import manager


def utc_now() -> datetime:
    """Return current UTC time as a naive datetime."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def serialize_text_value(value: Any) -> str | None:
    """Convert scanner values into database-safe text."""

    if value is None:
        return None

    if isinstance(value, str):
        return value

    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def get_last_scan(
    db: Session,
    site: Site,
) -> Scan | None:
    """Return the latest scan for this site."""

    return (
        db.query(Scan)
        .filter(Scan.site_id == site.id)
        .order_by(Scan.created_at.desc())
        .first()
    )


def is_scan_due(
    site: Site,
    last_scan: Scan | None,
) -> bool:
    """Determine whether a monitoring scan is due."""

    if last_scan is None:
        return True

    if last_scan.created_at is None:
        return True

    now = utc_now()

    elapsed_seconds = (
        now - last_scan.created_at
    ).total_seconds()

    interval_minutes = (
        site.monitoring_interval_minutes or 1
    )

    interval_seconds = interval_minutes * 60

    return elapsed_seconds >= interval_seconds


def parse_json_value(
    value: str | None,
) -> Any:
    """Safely convert stored JSON text back into Python."""

    if value is None:
        return None

    try:
        return json.loads(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return value


def build_event_payload(event) -> dict:
    """Convert MonitoringEvent ORM object into WebSocket data."""

    return {
        "event_id": str(event.id),
        "site_id": str(event.site_id),
        "scan_id": str(event.scan_id),
        "event_type": event.event_type,
        "severity": event.severity,
        "title": event.title,
        "description": event.description,
        "previous_value": parse_json_value(
            event.previous_value
        ),
        "current_value": parse_json_value(
            event.current_value
        ),
        "created_at": (
            event.created_at.isoformat()
            if event.created_at
            else None
        ),
    }


def build_alert_payload(alert) -> dict:
    """Convert Alert ORM object into WebSocket data."""

    return {
        "alert_id": str(alert.id),
        "site_id": str(alert.site_id),
        "event_id": (
            str(alert.event_id)
            if alert.event_id is not None
            else None
        ),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "is_read": alert.is_read,
        "created_at": (
            alert.created_at.isoformat()
            if alert.created_at
            else None
        ),
    }


def broadcast_monitoring_update(
    site: Site,
    scan: Scan,
    events: list,
    alerts: list,
) -> None:
    """Broadcast monitoring update to connected WebSocket clients."""

    message = {
        "type": "monitoring_update",
        "timestamp": utc_now().isoformat(),

        "site": {
            "site_id": str(site.id),
            "name": site.name,
            "url": site.url,
            "hostname": site.hostname,
        },

        "scan": {
            "scan_id": str(scan.id),
            "status": scan.status,
            "status_code": scan.status_code,
            "response_time_ms": scan.response_time_ms,
            "ip_address": scan.ip_address,
            "risk_score": scan.risk_score,
            "risk_level": scan.risk_level,
            "findings_count": scan.findings_count,
        },

        "events": [
            build_event_payload(event)
            for event in events
        ],

        "alerts": [
            build_alert_payload(alert)
            for alert in alerts
        ],

        "summary": {
            "events_count": len(events),
            "alerts_count": len(alerts),
        },
    }

    print(
        "[WEBSOCKET] Broadcasting monitoring_update "
        f"for site #{site.id}"
    )

    manager.broadcast_sync(message)


def persist_scan(
    db: Session,
    site: Site,
    scan_result: dict,
    previous_scan: Scan | None = None,
) -> Scan:
    """
    Persist scan, detect changes, create alerts,
    and broadcast the monitoring update.
    """

    availability = scan_result.get("availability") or {}
    ssl_result = scan_result.get("ssl") or {}

    security_headers = (
        scan_result.get("security_headers") or {}
    )

    risk = scan_result.get("risk") or {}

    findings = risk.get("findings") or []

    severity_counts: dict[str, int] = {}

    for finding in findings:
        if not isinstance(finding, dict):
            continue

        severity = finding.get(
            "severity",
            "unknown",
        )

        severity_counts[severity] = (
            severity_counts.get(severity, 0) + 1
        )

    # ========================================================
    # CREATE SCAN
    # ========================================================

    scan = Scan(
        site_id=site.id,

        target_url=scan_result.get(
            "target",
            site.url,
        ),

        hostname=availability.get(
            "hostname",
            site.hostname,
        ),

        status=availability.get(
            "status",
            "unknown",
        ),

        status_code=availability.get(
            "status_code",
        ),

        response_time_ms=availability.get(
            "response_time_ms",
        ),

        ip_address=availability.get(
            "ip_address",
        ),

        # SSL enabled comes from availability.
        ssl_enabled=availability.get(
            "ssl_enabled",
            False,
        ),

        ssl_valid=ssl_result.get(
            "valid",
            False,
        ),

        ssl_issuer=serialize_text_value(
            ssl_result.get("issuer")
        ),

        ssl_subject=serialize_text_value(
            ssl_result.get("subject")
        ),

        ssl_error=serialize_text_value(
            ssl_result.get("error")
        ),

        security_headers_score=security_headers.get(
            "score",
            0,
        ),

        security_headers_total=security_headers.get(
            "total",
            0,
        ),

        security_headers=serialize_text_value(
            security_headers.get(
                "headers",
                {},
            )
        ),

        missing_headers=serialize_text_value(
            security_headers.get(
                "missing",
                [],
            )
        ),

        security_headers_error=serialize_text_value(
            security_headers.get("error")
        ),

        risk_score=risk.get(
            "score",
            100,
        ),

        # Scanner returns risk_level.
        risk_level=risk.get(
            "risk_level",
            "low",
        ),

        findings_count=len(findings),

        severity_counts=json.dumps(
            severity_counts
        ),

        findings=json.dumps(
            findings
        ),
    )

    db.add(scan)

    # IMPORTANT:
    # Make scan.id available before creating events.
    db.flush()

    # ========================================================
    # UPDATE SITE SNAPSHOT
    # ========================================================

    site.last_scan_id = scan.id
    site.last_status = scan.status
    site.last_risk_score = scan.risk_score
    site.last_risk_level = scan.risk_level
    site.updated_at = utc_now()

    # ========================================================
    # DETECT CHANGES
    # ========================================================

    events = detect_scan_changes(
        db=db,
        site=site,
        previous_scan=previous_scan,
        current_scan=scan,
    )

    # IMPORTANT:
    # detect_scan_changes() uses db.add(event).
    #
    # Database-generated event IDs are not guaranteed to
    # exist until SQLAlchemy flushes the pending INSERTs.
    #
    # Therefore flush events BEFORE creating alerts.
    if events:
        db.flush()

    # ========================================================
    # CREATE ALERTS
    # ========================================================

    alerts = create_alerts_from_events(
        db=db,
        events=events,
    )

    # IMPORTANT:
    # Flush alerts so their IDs are available for the
    # WebSocket payload before commit.
    if alerts:
        db.flush()

    # ========================================================
    # COMMIT
    # ========================================================

    db.commit()

    db.refresh(scan)

    # Refresh generated event/alert fields after commit.
    for event in events:
        db.refresh(event)

    for alert in alerts:
        db.refresh(alert)

    print(
        f"[MONITORING] Created scan #{scan.id} "
        f"for site #{site.id}"
    )

    # ========================================================
    # EVENT LOG
    # ========================================================

    if events:
        print(
            f"[MONITORING] Detected "
            f"{len(events)} event(s)"
        )

        for event in events:
            print(
                f"[EVENT] {event.event_type} | "
                f"{event.severity} | "
                f"{event.title} | "
                f"id={event.id}"
            )

    else:
        print(
            "[MONITORING] No security changes detected."
        )

    # ========================================================
    # ALERT LOG
    # ========================================================

    if alerts:
        print(
            f"[ALERTS] Created "
            f"{len(alerts)} alert(s)"
        )

        for alert in alerts:
            print(
                f"[ALERT] {alert.severity} | "
                f"{alert.title} | "
                f"id={alert.id} | "
                f"event_id={alert.event_id}"
            )

    else:
        print(
            "[ALERTS] No alerts created."
        )

    # ========================================================
    # WEBSOCKET
    # ========================================================

    broadcast_monitoring_update(
        site=site,
        scan=scan,
        events=events,
        alerts=alerts,
    )

    return scan


def run_monitoring_scan(
    db: Session,
    site: Site,
    previous_scan: Scan | None = None,
) -> Scan:
    """Run scanner and persist the result."""

    print(
        f"[MONITORING] Running scanner for "
        f"{site.name} ({site.url})"
    )

    scan_result = run_site_scan(
        site.url
    )

    return persist_scan(
        db=db,
        site=site,
        scan_result=scan_result,
        previous_scan=previous_scan,
    )


def monitor_sites() -> dict:
    """Scan all enabled sites whose monitoring interval is due."""

    db = SessionLocal()

    scanned = []
    skipped = []
    failed = []

    try:
        sites = (
            db.query(Site)
            .filter(
                Site.monitoring_enabled.is_(True)
            )
            .all()
        )

        print(
            f"[MONITORING] Enabled sites found: "
            f"{len(sites)}"
        )

        for site in sites:

            try:
                last_scan = get_last_scan(
                    db,
                    site,
                )

                if not is_scan_due(
                    site,
                    last_scan,
                ):
                    skipped.append(
                        {
                            "site_id": site.id,
                            "name": site.name,
                            "reason": "interval_not_due",
                        }
                    )

                    continue

                print(
                    f"[MONITORING] Scanning site: "
                    f"{site.name} ({site.url})"
                )

                scan = run_monitoring_scan(
                    db=db,
                    site=site,
                    previous_scan=last_scan,
                )

                scanned.append(
                    {
                        "site_id": site.id,
                        "scan_id": scan.id,
                        "name": site.name,
                        "status": scan.status,
                        "risk_score": scan.risk_score,
                        "risk_level": scan.risk_level,
                    }
                )

                print(
                    f"[MONITORING] Scan completed: "
                    f"site={site.id}, "
                    f"scan={scan.id}, "
                    f"risk={scan.risk_score}, "
                    f"level={scan.risk_level}"
                )

            except Exception as exc:

                db.rollback()

                print(
                    f"[MONITORING ERROR] "
                    f"Site {site.id} ({site.name}) failed: "
                    f"{exc}"
                )

                failed.append(
                    {
                        "site_id": site.id,
                        "name": site.name,
                        "error": str(exc),
                    }
                )

        status = (
            "completed"
            if not failed
            else "completed_with_errors"
        )

        return {
            "status": status,
            "checked_sites": len(sites),
            "scanned": scanned,
            "skipped": skipped,
            "failed": failed,
        }

    finally:
        db.close()