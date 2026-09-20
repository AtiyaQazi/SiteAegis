import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import Site, Scan, MonitoringEvent


def safe_json_loads(value: Any) -> Any:
    """Safely decode JSON values."""

    if value is None:
        return None

    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def finding_key(finding: dict) -> str:
    """Create a stable identifier for a finding."""

    category = str(
        finding.get("category", "")
    ).strip().lower()

    title = str(
        finding.get("title", "")
    ).strip().lower()

    return f"{category}:{title}"


def build_finding_map(
    findings: list,
) -> dict[str, dict]:
    """Convert finding list into a keyed dictionary."""

    result = {}

    for finding in findings or []:
        if not isinstance(finding, dict):
            continue

        result[finding_key(finding)] = finding

    return result


def create_event(
    db: Session,
    site: Site,
    scan: Scan,
    event_type: str,
    severity: str,
    title: str,
    description: str,
    previous_value: Any = None,
    current_value: Any = None,
):
    """Create and stage a monitoring event."""

    event = MonitoringEvent(
        site_id=site.id,
        scan_id=scan.id,
        event_type=event_type,
        severity=severity,
        title=title,
        description=description,
        previous_value=json.dumps(
            previous_value
        )
        if previous_value is not None
        else None,
        current_value=json.dumps(
            current_value
        )
        if current_value is not None
        else None,
    )

    db.add(event)

    return event


def detect_finding_changes(
    db: Session,
    site: Site,
    previous_scan: Scan,
    current_scan: Scan,
) -> list:
    """Detect newly appeared and resolved findings."""

    previous_findings = safe_json_loads(
        previous_scan.findings
    ) or []

    current_findings = safe_json_loads(
        current_scan.findings
    ) or []

    previous_map = build_finding_map(
        previous_findings
    )

    current_map = build_finding_map(
        current_findings
    )

    events = []

    # --------------------------------------------------------
    # NEW FINDINGS
    # --------------------------------------------------------

    for key, finding in current_map.items():

        if key in previous_map:
            continue

        severity = finding.get(
            "severity",
            "medium",
        )

        event = create_event(
            db=db,
            site=site,
            scan=current_scan,
            event_type="NEW_FINDING",
            severity=severity,
            title=finding.get(
                "title",
                "New security finding",
            ),
            description=(
                finding.get("description")
                or "A new security finding was detected."
            ),
            previous_value=None,
            current_value=finding,
        )

        events.append(event)

    # --------------------------------------------------------
    # RESOLVED FINDINGS
    # --------------------------------------------------------

    for key, finding in previous_map.items():

        if key in current_map:
            continue

        event = create_event(
            db=db,
            site=site,
            scan=current_scan,
            event_type="RESOLVED_FINDING",
            severity="low",
            title=(
                f"Resolved: "
                f"{finding.get('title', 'Security finding')}"
            ),
            description=(
                "A previously detected security finding "
                "is no longer present."
            ),
            previous_value=finding,
            current_value=None,
        )

        events.append(event)

    return events


def detect_risk_change(
    db: Session,
    site: Site,
    previous_scan: Scan,
    current_scan: Scan,
) -> list:
    """
    Detect risk score changes.

    SiteAegis uses:
        100 = best
        lower score = higher risk

    Therefore:
        current < previous -> risk increased
        current > previous -> risk decreased
    """

    previous_score = previous_scan.risk_score
    current_score = current_scan.risk_score

    if previous_score is None or current_score is None:
        return []

    if previous_score == current_score:
        return []

    events = []

    # --------------------------------------------------------
    # RISK INCREASED
    # --------------------------------------------------------

    if current_score < previous_score:

        event = create_event(
            db=db,
            site=site,
            scan=current_scan,
            event_type="RISK_INCREASED",
            severity="high",
            title="Security risk increased",
            description=(
                f"Risk score decreased from "
                f"{previous_score} to {current_score}, "
                f"indicating increased security risk."
            ),
            previous_value={
                "score": previous_score,
                "risk_level": previous_scan.risk_level,
            },
            current_value={
                "score": current_score,
                "risk_level": current_scan.risk_level,
            },
        )

        events.append(event)

    # --------------------------------------------------------
    # RISK DECREASED
    # --------------------------------------------------------

    else:

        event = create_event(
            db=db,
            site=site,
            scan=current_scan,
            event_type="RISK_DECREASED",
            severity="low",
            title="Security risk decreased",
            description=(
                f"Risk score increased from "
                f"{previous_score} to {current_score}, "
                f"indicating decreased security risk."
            ),
            previous_value={
                "score": previous_score,
                "risk_level": previous_scan.risk_level,
            },
            current_value={
                "score": current_score,
                "risk_level": current_scan.risk_level,
            },
        )

        events.append(event)

    return events


def detect_status_change(
    db: Session,
    site: Site,
    previous_scan: Scan,
    current_scan: Scan,
) -> list:
    """Detect online/offline/status changes."""

    previous_status = previous_scan.status
    current_status = current_scan.status

    if previous_status == current_status:
        return []

    if current_status in (
        "unreachable",
        "offline",
    ):

        severity = "critical"
        event_type = "SITE_OFFLINE"
        title = "Website went offline"

    else:

        severity = "low"
        event_type = "SITE_STATUS_CHANGED"
        title = "Website status changed"

    event = create_event(
        db=db,
        site=site,
        scan=current_scan,
        event_type=event_type,
        severity=severity,
        title=title,
        description=(
            f"Website status changed from "
            f"{previous_status} to {current_status}."
        ),
        previous_value=previous_status,
        current_value=current_status,
    )

    return [event]


def detect_scan_changes(
    db: Session,
    site: Site,
    previous_scan: Scan | None,
    current_scan: Scan,
) -> list:
    """
    Detect all monitoring changes between
    previous and current scan.
    """

    # First scan has no baseline.
    if previous_scan is None:
        return []

    events = []

    events.extend(
        detect_finding_changes(
            db=db,
            site=site,
            previous_scan=previous_scan,
            current_scan=current_scan,
        )
    )

    events.extend(
        detect_risk_change(
            db=db,
            site=site,
            previous_scan=previous_scan,
            current_scan=current_scan,
        )
    )

    events.extend(
        detect_status_change(
            db=db,
            site=site,
            previous_scan=previous_scan,
            current_scan=current_scan,
        )
    )

    return events