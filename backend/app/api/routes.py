import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Scan
from app.schemas.common import SiteRequest
from app.services.site_service import run_site_scan


router = APIRouter(
    prefix="/scan",
    tags=["Scanner"],
)


# ============================================================
# RUN NEW SCAN
# ============================================================

@router.post("")
def scan_site(
    request: SiteRequest,
    db: Session = Depends(get_db),
):
    try:
        result = run_site_scan(request.url)

        availability = result.get(
            "availability",
            {},
        )

        ssl_result = result.get(
            "ssl",
            {},
        )

        headers = result.get(
            "security_headers",
            {},
        )

        risk = result.get(
            "risk",
            {},
        )

        # ----------------------------------------------------
        # SAVE COMPLETE SCAN DATA
        # ----------------------------------------------------

        scan = Scan(
            # Target
            target_url=result["target"],
            hostname=availability.get(
                "hostname",
                "",
            ),

            # Availability
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

            # SSL
            ssl_enabled=availability.get(
                "ssl_enabled",
                False,
            ),
            ssl_valid=ssl_result.get(
                "valid",
                False,
            ),
            ssl_issuer=json.dumps(
                ssl_result.get(
                    "issuer",
                )
            ),
            ssl_subject=json.dumps(
                ssl_result.get(
                    "subject",
                )
            ),
            ssl_error=ssl_result.get(
                "error",
            ),

            # Security Headers
            security_headers_score=headers.get(
                "score",
                0,
            ),
            security_headers_total=headers.get(
                "total",
                0,
            ),
            security_headers=json.dumps(
                headers.get(
                    "headers",
                    {},
                )
            ),
            missing_headers=json.dumps(
                headers.get(
                    "missing",
                    [],
                )
            ),
            security_headers_error=headers.get(
                "error",
            ),

            # Risk
            risk_score=risk.get(
                "score",
                0,
            ),
            risk_level=risk.get(
                "risk_level",
                "unknown",
            ),
            findings_count=risk.get(
                "findings_count",
                0,
            ),
            severity_counts=json.dumps(
                risk.get(
                    "severity_counts",
                    {},
                )
            ),
            findings=json.dumps(
                risk.get(
                    "findings",
                    [],
                )
            ),
        )

        db.add(scan)
        db.commit()
        db.refresh(scan)

        # ----------------------------------------------------
        # RETURN COMPLETE SCAN RESULT
        # ----------------------------------------------------

        return {
            "scan_id": str(scan.id),
            "target": result["target"],
            "availability": result["availability"],
            "security_headers": result["security_headers"],
            "ssl": result["ssl"],
            "risk": result["risk"],
            "created_at": scan.created_at,
        }

    except ValueError as exc:

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Site scan failed: {str(exc)}",
        )


# ============================================================
# SCAN HISTORY
# ============================================================

@router.get("/history")
def scan_history(
    db: Session = Depends(get_db),
):
    scans = (
        db.query(Scan)
        .order_by(Scan.created_at.desc())
        .all()
    )

    return [
        {
            "scan_id": str(scan.id),

            "url": scan.target_url,
            "hostname": scan.hostname,

            "status": scan.status,
            "status_code": scan.status_code,
            "response_time_ms": scan.response_time_ms,
            "ip_address": scan.ip_address,

            "ssl_enabled": scan.ssl_enabled,
            "ssl_valid": scan.ssl_valid,

            "security_headers_score": (
                scan.security_headers_score
            ),

            "risk_score": scan.risk_score,
            "risk_level": scan.risk_level,
            "findings_count": scan.findings_count,

            "created_at": scan.created_at,
        }
        for scan in scans
    ]


# ============================================================
# GET SINGLE COMPLETE SCAN
# ============================================================

@router.get("/{scan_id}")
def get_scan(
    scan_id: int,
    db: Session = Depends(get_db),
):
    scan = (
        db.query(Scan)
        .filter(Scan.id == scan_id)
        .first()
    )

    if not scan:

        raise HTTPException(
            status_code=404,
            detail="Scan not found.",
        )

    # --------------------------------------------------------
    # Decode JSON fields
    # --------------------------------------------------------

    ssl_issuer = None
    ssl_subject = None

    security_headers = {}
    missing_headers = []

    severity_counts = {}
    findings = []

    try:
        if scan.ssl_issuer:
            ssl_issuer = json.loads(
                scan.ssl_issuer
            )
    except json.JSONDecodeError:
        ssl_issuer = None

    try:
        if scan.ssl_subject:
            ssl_subject = json.loads(
                scan.ssl_subject
            )
    except json.JSONDecodeError:
        ssl_subject = None

    try:
        if scan.security_headers:
            security_headers = json.loads(
                scan.security_headers
            )
    except json.JSONDecodeError:
        security_headers = {}

    try:
        if scan.missing_headers:
            missing_headers = json.loads(
                scan.missing_headers
            )
    except json.JSONDecodeError:
        missing_headers = []

    try:
        if scan.severity_counts:
            severity_counts = json.loads(
                scan.severity_counts
            )
    except json.JSONDecodeError:
        severity_counts = {}

    try:
        if scan.findings:
            findings = json.loads(
                scan.findings
            )
    except json.JSONDecodeError:
        findings = []

    # --------------------------------------------------------
    # Complete response
    # --------------------------------------------------------

    return {
        "scan_id": str(scan.id),

        # ====================================================
        # TARGET
        # ====================================================

        "target": {
            "url": scan.target_url,
            "hostname": scan.hostname,
        },

        # ====================================================
        # AVAILABILITY
        # ====================================================

        "availability": {
            "status": scan.status,
            "status_code": scan.status_code,
            "response_time_ms": scan.response_time_ms,
            "ip_address": scan.ip_address,
        },

        # ====================================================
        # SSL / TLS
        # ====================================================

        "ssl": {
            "enabled": scan.ssl_enabled,
            "valid": scan.ssl_valid,
            "issuer": ssl_issuer,
            "subject": ssl_subject,
            "error": scan.ssl_error,
        },

        # ====================================================
        # SECURITY HEADERS
        # ====================================================

        "security_headers": {
            "score": scan.security_headers_score,
            "total": scan.security_headers_total,
            "headers": security_headers,
            "missing": missing_headers,
            "error": scan.security_headers_error,
        },

        # ====================================================
        # RISK
        # ====================================================

        "risk": {
            "score": scan.risk_score,
            "risk_level": scan.risk_level,
            "findings_count": scan.findings_count,
            "severity_counts": severity_counts,
            "findings": findings,
        },

        # ====================================================
        # TIMESTAMP
        # ====================================================

        "created_at": scan.created_at,
    }