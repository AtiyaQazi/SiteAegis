import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Site, Scan
from app.services.site_service import run_site_scan
from app.services.monitoring_events import detect_scan_changes
from app.services.alert_service import create_alerts_from_events
from app.services.redis_service import cache_latest_monitoring_update
from app.websocket.manager import manager


# ============================================================
# TIME HELPERS
# ============================================================


def utc_now() -> datetime:
    """
    Return current UTC time as a naive datetime.

    SiteAegis database timestamp columns are currently
    PostgreSQL `timestamp without time zone`.

    Existing SiteAegis records are stored using Pakistan
    local time (Asia/Karachi), so database timestamps must
    be normalized before UTC comparisons.
    """

    return datetime.now(timezone.utc).replace(
        tzinfo=None
    )


def database_time_to_utc(
    value: datetime | None,
) -> datetime | None:
    """
    Convert a database timestamp representing
    Asia/Karachi local time into a naive UTC datetime.

    PostgreSQL timestamp columns are currently
    `timestamp without time zone`.

    Example:

        DB: 14:51 Pakistan time
        UTC: 09:51

    The returned datetime remains naive so it can safely
    be compared with utc_now().
    """

    if value is None:
        return None

    from zoneinfo import ZoneInfo

    pakistan_timezone = ZoneInfo(
        "Asia/Karachi"
    )

    local_time = value.replace(
        tzinfo=pakistan_timezone
    )

    utc_time = local_time.astimezone(
        timezone.utc
    )

    return utc_time.replace(
        tzinfo=None
    )


# ============================================================
# SERIALIZATION HELPERS
# ============================================================


def serialize_text_value(
    value: Any,
) -> str | None:
    """
    Convert scanner values into database-safe text.

    SSL issuer/subject can be returned by Python's
    ssl module as nested tuples. JSON serialization
    converts those structures into database-safe strings.
    """

    if value is None:
        return None

    if isinstance(value, str):
        return value

    try:
        return json.dumps(value)

    except (TypeError, ValueError):
        return str(value)


# ============================================================
# SCAN HELPERS
# ============================================================


def get_last_scan(
    db: Session,
    site: Site,
) -> Scan | None:
    """
    Return the latest scan for this site.
    """

    return (
        db.query(Scan)
        .filter(
            Scan.site_id == site.id
        )
        .order_by(
            Scan.created_at.desc()
        )
        .first()
    )


def is_scan_due(
    site: Site,
    last_scan: Scan | None,
) -> bool:
    """
    Determine whether a monitoring scan is due.

    A site with no previous scan is immediately due.

    Database timestamps are currently stored as naive
    Asia/Karachi timestamps. They are converted to UTC
    before comparing with the current UTC time.
    """

    if last_scan is None:
        return True

    now = utc_now()

    last_scan_utc = database_time_to_utc(
        last_scan.created_at
    )

    if last_scan_utc is None:
        return True

    elapsed_seconds = (
        now - last_scan_utc
    ).total_seconds()

    interval_seconds = (
        site.monitoring_interval_minutes * 60
    )

    print(
        f"[MONITORING] Due check | "
        f"site={site.id} | "
        f"interval={site.monitoring_interval_minutes}m | "
        f"last_scan_db={last_scan.created_at} | "
        f"last_scan_utc={last_scan_utc} | "
        f"now_utc={now} | "
        f"elapsed={elapsed_seconds:.1f}s | "
        f"required={interval_seconds}s"
    )

    return elapsed_seconds >= interval_seconds


# ============================================================
# WEBSOCKET PAYLOAD HELPERS
# ============================================================


def build_event_payload(
    event: Any,
) -> dict[str, Any]:
    """
    Convert a MonitoringEvent model into a
    JSON-safe WebSocket payload.
    """

    return {
        "event_id": str(event.id),
        "site_id": str(event.site_id),
        "scan_id": str(event.scan_id),
        "event_type": event.event_type,
        "severity": event.severity,
        "title": event.title,
        "message": event.description,
        "created_at": (
            event.created_at.isoformat()
            if event.created_at
            else None
        ),
    }


def build_alert_payload(
    alert: Any,
) -> dict[str, Any]:
    """
    Convert an Alert model into a
    JSON-safe WebSocket payload.
    """

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


# ============================================================
# REDIS + WEBSOCKET
# ============================================================


def broadcast_monitoring_update(
    site: Site,
    scan: Scan,
    events: list,
    alerts: list,
) -> None:
    """
    Cache and broadcast the latest monitoring update.

    Redis is used as a fast cache.
    WebSocket is used for real-time dashboard updates.
    PostgreSQL remains the permanent source of truth.
    """

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

    # --------------------------------------------------------
    # REDIS CACHE
    # --------------------------------------------------------

    redis_cached = cache_latest_monitoring_update(
        site_id=site.id,
        payload=message,
    )

    if redis_cached:
        print(
            f"[REDIS] Cached latest monitoring update "
            f"for site #{site.id}"
        )

    else:
        print(
            f"[REDIS] Could not cache monitoring update "
            f"for site #{site.id}. "
            f"Continuing with WebSocket."
        )

    # --------------------------------------------------------
    # WEBSOCKET
    # --------------------------------------------------------

    print(
        "[WEBSOCKET] Broadcasting monitoring_update "
        f"for site #{site.id}"
    )

    manager.broadcast_sync(
        message
    )


# ============================================================
# SCAN PERSISTENCE
# ============================================================


def persist_scan(
    db: Session,
    site: Site,
    scan_result: dict,
    previous_scan: Scan | None = None,
) -> Scan:
    """
    Convert scanner output into a Scan database record,
    detect monitoring changes, create alerts for those
    events, persist everything, cache the latest state
    in Redis, and broadcast the update through WebSocket.
    """

    availability = (
        scan_result.get("availability")
        or {}
    )

    ssl = (
        scan_result.get("ssl")
        or {}
    )

    security_headers = (
        scan_result.get("security_headers")
        or {}
    )

    risk = (
        scan_result.get("risk")
        or {}
    )

    findings = (
        risk.get("findings")
        or []
    )

    severity_counts: dict[str, int] = {}

    for finding in findings:
        severity = finding.get(
            "severity",
            "unknown",
        )

        severity_counts[severity] = (
            severity_counts.get(
                severity,
                0,
            ) + 1
        )

    # --------------------------------------------------------
    # CREATE SCAN RECORD
    # --------------------------------------------------------

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

        ssl_enabled=ssl.get(
            "enabled",
            False,
        ),

        ssl_valid=ssl.get(
            "valid",
            False,
        ),

        ssl_issuer=serialize_text_value(
            ssl.get("issuer")
        ),

        ssl_subject=serialize_text_value(
            ssl.get("subject")
        ),

        ssl_error=serialize_text_value(
            ssl.get("error")
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
            security_headers.get(
                "error"
            )
        ),

        risk_score=risk.get(
            "score",
            100,
        ),

        # IMPORTANT:
        # site_service.calculate_risk() returns
        # "risk_level", not "level".
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

    # Flush first so scan.id exists before
    # monitoring events reference this scan.
    db.flush()

    # --------------------------------------------------------
    # UPDATE SITE LATEST SCAN SNAPSHOT
    # --------------------------------------------------------

    site.last_scan_id = scan.id
    site.last_status = scan.status
    site.last_risk_score = scan.risk_score
    site.last_risk_level = scan.risk_level
    site.updated_at = utc_now()

    # --------------------------------------------------------
    # DETECT MONITORING CHANGES
    # --------------------------------------------------------

    events = detect_scan_changes(
        db=db,
        site=site,
        previous_scan=previous_scan,
        current_scan=scan,
    )

    # --------------------------------------------------------
    # CREATE USER-FACING ALERTS
    # --------------------------------------------------------

    alerts = create_alerts_from_events(
        db=db,
        events=events,
    )

    # --------------------------------------------------------
    # COMMIT SCAN + EVENTS + ALERTS TOGETHER
    # --------------------------------------------------------

    db.commit()

    db.refresh(scan)

    # --------------------------------------------------------
    # MONITORING LOGGING
    # --------------------------------------------------------

    print(
        f"[MONITORING] "
        f"Created scan #{scan.id} "
        f"for site #{site.id}"
    )

    # --------------------------------------------------------
    # EVENT LOGGING
    # --------------------------------------------------------

    if events:

        print(
            f"[MONITORING] "
            f"Detected {len(events)} event(s)"
        )

        for event in events:

            print(
                f"[EVENT] "
                f"{event.event_type} | "
                f"{event.severity} | "
                f"{event.title}"
            )

    else:

        print(
            "[MONITORING] "
            "No security changes detected."
        )

    # --------------------------------------------------------
    # ALERT LOGGING
    # --------------------------------------------------------

    if alerts:

        print(
            f"[ALERTS] "
            f"Created {len(alerts)} alert(s)"
        )

        for alert in alerts:

            print(
                f"[ALERT] "
                f"{alert.severity} | "
                f"{alert.title}"
            )

    else:

        print(
            "[ALERTS] "
            "No alerts created."
        )

    # --------------------------------------------------------
    # REDIS + WEBSOCKET
    # --------------------------------------------------------
    #
    # PostgreSQL transaction has already been committed.
    # Redis is only a cache. If Redis fails, monitoring
    # should continue and WebSocket should still work.
    #

    broadcast_monitoring_update(
        site=site,
        scan=scan,
        events=events,
        alerts=alerts,
    )

    return scan


# ============================================================
# RUN ONE MONITORING SCAN
# ============================================================


def run_monitoring_scan(
    db: Session,
    site: Site,
    previous_scan: Scan | None = None,
) -> Scan:
    """
    Run a scanner scan for one registered site
    and persist the result.

    The previous scan is passed to the persistence
    layer so security changes can be detected.
    """

    scan_result = run_site_scan(
        site.url
    )

    return persist_scan(
        db=db,
        site=site,
        scan_result=scan_result,
        previous_scan=previous_scan,
    )


# ============================================================
# MONITOR ALL SITES
# ============================================================


def monitor_sites() -> dict:
    """
    Check all enabled monitoring sites and
    scan only the sites whose interval is due.
    """

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

        for site in sites:

            try:

                # --------------------------------------------
                # GET PREVIOUS SCAN
                # --------------------------------------------

                last_scan = get_last_scan(
                    db,
                    site,
                )

                # --------------------------------------------
                # CHECK MONITORING INTERVAL
                # --------------------------------------------

                if not is_scan_due(
                    site,
                    last_scan,
                ):

                    skipped.append(
                        {
                            "site_id": site.id,
                            "name": site.name,
                            "reason": (
                                "interval_not_due"
                            ),
                        }
                    )

                    continue

                # --------------------------------------------
                # RUN MONITORING SCAN
                # --------------------------------------------

                print(
                    f"[MONITORING] "
                    f"Scanning site: "
                    f"{site.name} "
                    f"({site.url})"
                )

                scan = run_monitoring_scan(
                    db=db,
                    site=site,
                    previous_scan=last_scan,
                )

                # --------------------------------------------
                # STORE RESULT
                # --------------------------------------------

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
                    f"[MONITORING] "
                    f"Scan completed: "
                    f"site={site.id}, "
                    f"scan={scan.id}, "
                    f"risk={scan.risk_score}, "
                    f"level={scan.risk_level}"
                )

            except Exception as exc:

                # Roll back only the failed site's
                # transaction so the monitoring loop
                # can continue with other sites.

                db.rollback()

                print(
                    f"[MONITORING ERROR] "
                    f"Site {site.id} "
                    f"({site.name}) failed: "
                    f"{exc}"
                )

                failed.append(
                    {
                        "site_id": site.id,
                        "name": site.name,
                        "error": str(exc),
                    }
                )

        # ----------------------------------------------------
        # FINAL MONITORING STATUS
        # ----------------------------------------------------

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