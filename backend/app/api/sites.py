import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Site, Scan
from app.models.monitoring_event import MonitoringEvent
from app.schemas.common import SiteRequest, ScanResponse
from app.schemas.site import (
    SiteCreate,
    SiteUpdate,
    SiteResponse,
)
from app.schemas.monitoring_event import (
    MonitoringEventResponse,
)
from app.services.site_service import (
    get_hostname,
    normalize_url,
    run_site_scan,
)


router = APIRouter(
    prefix="/sites",
    tags=["Sites"],
)


# ============================================================
# HELPERS
# ============================================================

def build_site_response(site: Site) -> SiteResponse:
    """
    Convert a Site database object into the public API response.
    """

    return SiteResponse(
        site_id=str(site.id),
        name=site.name,
        url=site.url,
        hostname=site.hostname,

        monitoring_enabled=site.monitoring_enabled,
        monitoring_interval_minutes=(
            site.monitoring_interval_minutes
        ),

        last_scan_id=(
            str(site.last_scan_id)
            if site.last_scan_id is not None
            else None
        ),

        last_status=site.last_status,
        last_risk_score=site.last_risk_score,
        last_risk_level=site.last_risk_level,

        created_at=site.created_at,
        updated_at=site.updated_at,
    )


def safe_json_loads(value):
    """
    Safely decode JSON stored inside database text fields.
    """

    if value is None:
        return None

    try:
        return json.loads(value)
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return value


def build_scan_summary(scan: Scan) -> dict:
    """
    Convert a Scan database object into a compact API response.
    """

    return {
        "scan_id": str(scan.id),
        "site_id": (
            str(scan.site_id)
            if scan.site_id is not None
            else None
        ),
        "target_url": scan.target_url,
        "hostname": scan.hostname,
        "status": scan.status,
        "status_code": scan.status_code,
        "response_time_ms": scan.response_time_ms,
        "ip_address": scan.ip_address,

        "ssl": {
            "enabled": scan.ssl_enabled,
            "valid": scan.ssl_valid,
            "issuer": safe_json_loads(
                scan.ssl_issuer
            ),
            "subject": safe_json_loads(
                scan.ssl_subject
            ),
            "error": safe_json_loads(
                scan.ssl_error
            ),
        },

        "security_headers": {
            "score": scan.security_headers_score,
            "total": scan.security_headers_total,
            "headers": safe_json_loads(
                scan.security_headers
            ),
            "missing": safe_json_loads(
                scan.missing_headers
            ),
            "error": safe_json_loads(
                scan.security_headers_error
            ),
        },

        "risk": {
            "score": scan.risk_score,
            "level": scan.risk_level,
        },

        "findings_count": scan.findings_count,

        "severity_counts": safe_json_loads(
            scan.severity_counts
        ),

        "created_at": scan.created_at,
    }


# ============================================================
# CREATE SITE
# ============================================================

@router.post(
    "",
    response_model=SiteResponse,
    status_code=201,
)
def create_site(
    payload: SiteCreate,
    db: Session = Depends(get_db),
):
    """
    Register a new website for SiteAegis monitoring.
    """

    try:
        normalized_url = normalize_url(
            payload.url
        )

        hostname = get_hostname(
            normalized_url
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    existing_site = (
        db.query(Site)
        .filter(
            Site.url == normalized_url
        )
        .first()
    )

    if existing_site:
        raise HTTPException(
            status_code=409,
            detail="This website is already registered.",
        )

    site = Site(
        name=payload.name.strip(),
        url=normalized_url,
        hostname=hostname,
        monitoring_enabled=True,
        monitoring_interval_minutes=(
            payload.monitoring_interval_minutes
        ),
    )

    db.add(site)
    db.commit()
    db.refresh(site)

    return build_site_response(site)


# ============================================================
# LIST SITES
# ============================================================

@router.get(
    "",
    response_model=list[SiteResponse],
)
def get_sites(
    db: Session = Depends(get_db),
):
    """
    Return all registered websites.
    """

    sites = (
        db.query(Site)
        .order_by(
            Site.created_at.desc()
        )
        .all()
    )

    return [
        build_site_response(site)
        for site in sites
    ]


# ============================================================
# GET SINGLE SITE
# ============================================================

@router.get(
    "/{site_id}",
    response_model=SiteResponse,
)
def get_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Return one registered website.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    return build_site_response(site)


# ============================================================
# UPDATE SITE
# ============================================================

@router.patch(
    "/{site_id}",
    response_model=SiteResponse,
)
def update_site(
    site_id: int,
    payload: SiteUpdate,
    db: Session = Depends(get_db),
):
    """
    Update monitoring settings for a registered site.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    if payload.name is not None:
        site.name = payload.name.strip()

    if payload.monitoring_enabled is not None:
        site.monitoring_enabled = (
            payload.monitoring_enabled
        )

    if (
        payload.monitoring_interval_minutes
        is not None
    ):
        site.monitoring_interval_minutes = (
            payload.monitoring_interval_minutes
        )

    db.commit()
    db.refresh(site)

    return build_site_response(site)


# ============================================================
# DELETE SITE
# ============================================================

@router.delete(
    "/{site_id}",
)
def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a registered website.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    db.delete(site)
    db.commit()

    return {
        "status": "deleted",
        "site_id": str(site_id),
        "message": "Site deleted successfully.",
    }


# ============================================================
# MANUAL SITE SCAN
# ============================================================

@router.post(
    "/{site_id}/scan",
    response_model=ScanResponse,
)
def scan_site(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Run a manual security scan for a registered site.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    if not site.monitoring_enabled:
        raise HTTPException(
            status_code=400,
            detail=(
                "Monitoring is disabled for this site. "
                "Enable monitoring before running a scan."
            ),
        )

    try:
        result = run_site_scan(
            site.url
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Scan failed: {exc}",
        )

    availability = (
        result.get("availability")
        or {}
    )

    scan_id = (
        str(site.last_scan_id)
        if site.last_scan_id is not None
        else ""
    )

    return ScanResponse(
        scan_id=scan_id,
        url=site.url,
        status=availability.get(
            "status",
            "unknown",
        ),
        message=(
            "Manual scan completed. "
            "Use scan history for persisted scan details."
        ),
    )


# ============================================================
# SCAN HISTORY
# ============================================================

@router.get(
    "/{site_id}/scans",
)
def get_site_scans(
    site_id: int,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
):
    """
    Return scan history for a registered site.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    scans = (
        db.query(Scan)
        .filter(
            Scan.site_id == site.id
        )
        .order_by(
            Scan.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    return [
        build_scan_summary(scan)
        for scan in scans
    ]


# ============================================================
# ALL FINDINGS FOR SITE
# ============================================================

@router.get(
    "/{site_id}/findings",
)
def get_site_findings(
    site_id: int,
    db: Session = Depends(get_db),
):
    """
    Return findings from the latest scan of a site.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    latest_scan = (
        db.query(Scan)
        .filter(
            Scan.site_id == site.id
        )
        .order_by(
            Scan.created_at.desc()
        )
        .first()
    )

    if not latest_scan:
        return {
            "site_id": str(site.id),
            "scan_id": None,
            "findings": [],
        }

    findings = safe_json_loads(
        latest_scan.findings
    )

    if not isinstance(findings, list):
        findings = []

    return {
        "site_id": str(site.id),
        "scan_id": str(latest_scan.id),
        "findings": findings,
    }


# ============================================================
# FINDINGS FOR SPECIFIC SCAN
# ============================================================

@router.get(
    "/{site_id}/scans/{scan_id}/findings",
)
def get_scan_findings(
    site_id: int,
    scan_id: int,
    db: Session = Depends(get_db),
):
    """
    Return findings for a specific scan.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    scan = (
        db.query(Scan)
        .filter(
            Scan.id == scan_id,
            Scan.site_id == site.id,
        )
        .first()
    )

    if not scan:
        raise HTTPException(
            status_code=404,
            detail="Scan not found for this site.",
        )

    findings = safe_json_loads(
        scan.findings
    )

    if not isinstance(findings, list):
        findings = []

    return {
        "site_id": str(site.id),
        "scan_id": str(scan.id),
        "findings": findings,
    }


# ============================================================
# SITE TREND
# ============================================================

@router.get(
    "/{site_id}/trend",
)
def get_site_trend(
    site_id: int,
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    """
    Return risk and availability trend for a site.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    scans = (
        db.query(Scan)
        .filter(
            Scan.site_id == site.id
        )
        .order_by(
            Scan.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    scans.reverse()

    trend = []

    for scan in scans:
        trend.append(
            {
                "scan_id": str(scan.id),
                "created_at": scan.created_at,
                "status": scan.status,
                "status_code": scan.status_code,
                "risk_score": scan.risk_score,
                "risk_level": scan.risk_level,
                "response_time_ms": (
                    scan.response_time_ms
                ),
                "security_headers_score": (
                    scan.security_headers_score
                ),
                "security_headers_total": (
                    scan.security_headers_total
                ),
                "findings_count": (
                    scan.findings_count
                ),
            }
        )

    return {
        "site_id": str(site.id),
        "site_name": site.name,
        "points": trend,
    }


# ============================================================
# MONITORING EVENTS
# ============================================================

@router.get(
    "/{site_id}/events",
    response_model=list[
        MonitoringEventResponse
    ],
)
def get_site_events(
    site_id: int,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
):
    """
    Return monitoring events for a registered site.

    Events are returned newest first.
    """

    site = (
        db.query(Site)
        .filter(
            Site.id == site_id
        )
        .first()
    )

    if not site:
        raise HTTPException(
            status_code=404,
            detail="Site not found.",
        )

    events = (
        db.query(MonitoringEvent)
        .filter(
            MonitoringEvent.site_id == site.id
        )
        .order_by(
            MonitoringEvent.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    result = []

    for event in events:

        previous_value = safe_json_loads(
            event.previous_value
        )

        current_value = safe_json_loads(
            event.current_value
        )

        result.append(
            MonitoringEventResponse(
                event_id=str(event.id),
                site_id=str(event.site_id),
                scan_id=str(event.scan_id),
                event_type=event.event_type,
                severity=event.severity,
                title=event.title,
                description=event.description,
                previous_value=previous_value,
                current_value=current_value,
                created_at=event.created_at,
            )
        )

    return result