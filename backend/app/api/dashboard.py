from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Scan


router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"],
)


# ============================================================
# DASHBOARD STATS
# ============================================================

@router.get("/stats")
def dashboard_stats(
    db: Session = Depends(get_db),
):
    scans = (
        db.query(Scan)
        .order_by(Scan.created_at.desc())
        .all()
    )

    total_scans = len(scans)

    # ========================================================
    # OVERVIEW
    # ========================================================

    online_sites = sum(
        1 for scan in scans
        if scan.status == "online"
    )

    offline_sites = sum(
        1 for scan in scans
        if scan.status != "online"
    )

    ssl_valid_scans = sum(
        1 for scan in scans
        if scan.ssl_valid
    )

    ssl_invalid_scans = sum(
        1 for scan in scans
        if not scan.ssl_valid
    )

    risk_scores = [
        scan.risk_score
        for scan in scans
    ]

    response_times = [
        scan.response_time_ms
        for scan in scans
        if scan.response_time_ms is not None
    ]

    header_scores = [
        scan.security_headers_score
        for scan in scans
    ]

    average_risk_score = (
        sum(risk_scores) / len(risk_scores)
        if risk_scores
        else 0
    )

    average_response_time_ms = (
        sum(response_times) / len(response_times)
        if response_times
        else 0
    )

    average_security_headers_score = (
        sum(header_scores) / len(header_scores)
        if header_scores
        else 0
    )

    # ========================================================
    # RISK DISTRIBUTION
    # ========================================================

    risk_distribution = {
        "low": 0,
        "medium": 0,
        "high": 0,
        "critical": 0,
    }

    for scan in scans:

        risk_level = scan.risk_level.lower()

        if risk_level in risk_distribution:
            risk_distribution[risk_level] += 1

    # ========================================================
    # SEVERITY DISTRIBUTION
    # ========================================================

    severity_distribution = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
    }

    for scan in scans:

        if not scan.severity_counts:
            continue

        try:
            import json

            counts = json.loads(
                scan.severity_counts
            )

            for severity in severity_distribution:

                severity_distribution[severity] += int(
                    counts.get(
                        severity,
                        0,
                    )
                )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ):
            continue

    # ========================================================
    # HEADER ANALYSIS
    # ========================================================

    missing_header_counter = Counter()

    for scan in scans:

        if not scan.missing_headers:
            continue

        try:
            import json

            missing = json.loads(
                scan.missing_headers
            )

            for header in missing:
                missing_header_counter[header] += 1

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

    most_missing_headers = [
        {
            "header": header,
            "count": count,
        }
        for header, count
        in missing_header_counter.most_common()
    ]

    # ========================================================
    # SCAN ACTIVITY
    # ========================================================

    activity_counter = Counter()

    for scan in scans:

        if not scan.created_at:
            continue

        date_key = scan.created_at.strftime(
            "%Y-%m-%d"
        )

        activity_counter[date_key] += 1

    scan_activity = [
        {
            "date": date,
            "scans": count,
        }
        for date, count
        in sorted(activity_counter.items())
    ]

    # ========================================================
    # RECENT SCANS
    # ========================================================

    recent_scans = [
        {
            "scan_id": str(scan.id),
            "url": scan.target_url,
            "hostname": scan.hostname,
            "status": scan.status,
            "status_code": scan.status_code,
            "risk_score": scan.risk_score,
            "risk_level": scan.risk_level,
            "response_time_ms": scan.response_time_ms,
            "ssl_valid": scan.ssl_valid,
            "security_headers_score": (
                scan.security_headers_score
            ),
            "findings_count": scan.findings_count,
            "created_at": scan.created_at,
        }
        for scan in scans[:10]
    ]

    # ========================================================
    # RETURN DASHBOARD DATA
    # ========================================================

    return {
        "overview": {
            "total_scans": total_scans,
            "online_sites": online_sites,
            "offline_sites": offline_sites,
            "average_risk_score": round(
                average_risk_score,
                2,
            ),
            "average_response_time_ms": round(
                average_response_time_ms,
                2,
            ),
            "average_security_headers_score": round(
                average_security_headers_score,
                2,
            ),
            "ssl_valid_scans": ssl_valid_scans,
            "ssl_invalid_scans": ssl_invalid_scans,
        },

        "risk_distribution": risk_distribution,

        "severity_distribution": severity_distribution,

        "header_analysis": {
            "average_score": round(
                average_security_headers_score,
                2,
            ),
            "most_missing_headers": most_missing_headers,
        },

        "scan_activity": scan_activity,

        "recent_scans": recent_scans,
    }