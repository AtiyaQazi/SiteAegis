import json
from io import BytesIO
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from PIL import Image
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Scan
from app.schemas.common import SiteRequest
from app.schemas.safety_event import SafetyEventCreate
from app.services.site_service import run_site_scan
from app.services.vision_service import analyze_ppe_image
from app.services.safety_service import create_safety_event
from app.services.incident_service import get_incident_by_event


router = APIRouter(
    prefix="/scan",
    tags=["Scanner"],
)


# ============================================================
# PPE VIOLATION CONFIGURATION
# ============================================================

PPE_VIOLATION_CONFIG = {
    "helmet": {
        "event_type": "helmet_violation",
        "title": "Helmet / Hardhat Violation",
        "detected_object": "no-hardhat",
    },
    "vest": {
        "event_type": "vest_violation",
        "title": "Safety Vest Violation",
        "detected_object": "no-safety vest",
    },
    "gloves": {
        "event_type": "gloves_violation",
        "title": "Safety Gloves Violation",
        "detected_object": "no-gloves",
    },
    "boots": {
        "event_type": "boots_violation",
        "title": "Safety Boots Violation",
        "detected_object": "no-boots",
    },
    "mask": {
        "event_type": "mask_violation",
        "title": "Safety Mask Violation",
        "detected_object": "no-mask",
    },
}


# ============================================================
# PPE VIOLATION -> SAFETY EVENT
# ============================================================

def create_safety_events_from_ppe(
    db: Session,
    ppe_analysis: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:

    safety_events: list[dict[str, Any]] = []
    incidents_created: list[dict[str, Any]] = []

    violations = ppe_analysis.get(
        "violations",
        [],
    )

    violation_summary = ppe_analysis.get(
        "violation_summary",
        {},
    )

    detections = ppe_analysis.get(
        "detections",
        [],
    )

    if not violations:
        return safety_events, incidents_created

    for violation_key, config in PPE_VIOLATION_CONFIG.items():

        violation_count = violation_summary.get(
            violation_key,
            0,
        )

        matching_violations = []

        for violation in violations:

            if isinstance(violation, dict):

                label = str(
                    violation.get(
                        "label",
                        "",
                    )
                ).lower()

                violation_type = str(
                    violation.get(
                        "violation_type",
                        violation.get(
                            "event_type",
                            "",
                        ),
                    )
                ).lower()

                if (
                    violation_key in label
                    or violation_key in violation_type
                ):
                    matching_violations.append(
                        violation
                    )

            elif isinstance(violation, str):

                if violation_key in violation.lower():
                    matching_violations.append(
                        violation
                    )

        if violation_count <= 0 and not matching_violations:
            continue

        if violation_count <= 0:
            violation_count = len(
                matching_violations
            )

        if violation_count <= 0:
            violation_count = 1

        confidence_values: list[float] = []

        for detection in detections:

            if not isinstance(
                detection,
                dict,
            ):
                continue

            label = str(
                detection.get(
                    "label",
                    "",
                )
            ).lower()

            if (
                violation_key in label
                or config["detected_object"] in label
            ):

                raw_confidence = detection.get(
                    "confidence"
                )

                if raw_confidence is not None:

                    try:
                        confidence_values.append(
                            float(raw_confidence)
                        )
                    except (
                        TypeError,
                        ValueError,
                    ):
                        pass

        confidence = (
            max(confidence_values)
            if confidence_values
            else None
        )

        description = (
            f"{violation_count} construction worker PPE "
            f"violation(s) detected by the SiteAegis vision "
            f"model."
        )

        if confidence is not None:

            description += (
                f" Highest detection confidence: "
                f"{confidence:.2f}."
            )

        event_data = SafetyEventCreate(
            camera_id=None,
            zone_id=None,
            event_type=config["event_type"],
            severity="high",
            title=config["title"],
            description=description,
            confidence=confidence,
            detected_object=config["detected_object"],
            risk_score=85,
            status="active",
        )

        try:

            event = create_safety_event(
                db=db,
                event_data=event_data,
            )

        except ValueError:
            raise

        safety_events.append(
            {
                "event_id": event.id,
                "event_type": event.event_type,
                "severity": event.severity,
                "title": event.title,
                "description": event.description,
                "confidence": event.confidence,
                "detected_object": event.detected_object,
                "risk_score": event.risk_score,
                "status": event.status,
                "occurred_at": event.occurred_at,
                "created_at": event.created_at,
            }
        )

        incident = get_incident_by_event(
            db=db,
            event_id=event.id,
        )

        if incident is not None:

            incidents_created.append(
                {
                    "incident_id": incident.id,
                    "event_id": incident.event_id,
                    "title": incident.title,
                    "incident_type": incident.incident_type,
                    "severity": incident.severity,
                    "risk_score": incident.risk_score,
                    "status": incident.status,
                    "created_at": incident.created_at,
                }
            )

    return (
        safety_events,
        incidents_created,
    )


# ============================================================
# RUN NEW WEBSITE SCAN
# ============================================================

@router.post("")
def scan_site(
    request: SiteRequest,
    db: Session = Depends(get_db),
):

    try:

        result = run_site_scan(
            request.url
        )

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

        scan = Scan(
            target_url=result["target"],

            hostname=availability.get(
                "hostname",
                "",
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
# PPE / CONSTRUCTION IMAGE ANALYSIS
# ============================================================

@router.post("/ppe")
async def analyze_ppe(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    try:

        # ----------------------------------------------------
        # Validate file type
        # ----------------------------------------------------

        if not file.content_type:

            raise HTTPException(
                status_code=400,
                detail="File type could not be detected.",
            )

        if not file.content_type.startswith(
            "image/"
        ):

            raise HTTPException(
                status_code=400,
                detail="Please upload an image file.",
            )

        # ----------------------------------------------------
        # Read uploaded image
        # ----------------------------------------------------

        image_bytes = await file.read()

        if not image_bytes:

            raise HTTPException(
                status_code=400,
                detail="Uploaded image is empty.",
            )

        # ----------------------------------------------------
        # Convert bytes -> PIL Image
        # ----------------------------------------------------

        try:

            image = Image.open(
                BytesIO(image_bytes)
            ).convert("RGB")

        except Exception:

            raise HTTPException(
                status_code=400,
                detail="Uploaded file is not a valid image.",
            )

        # ----------------------------------------------------
        # Run PPE detection
        # ----------------------------------------------------

        result = analyze_ppe_image(
            image=image,
            minimum_confidence=0.25,
        )

        # ----------------------------------------------------
        # Create SafetyEvents + Incidents
        # ----------------------------------------------------

        safety_events: list[dict[str, Any]] = []
        incidents_created: list[dict[str, Any]] = []

        if result.get(
            "evidence_sufficient",
            False,
        ):

            try:

                (
                    safety_events,
                    incidents_created,
                ) = create_safety_events_from_ppe(
                    db=db,
                    ppe_analysis=result,
                )

            except ValueError as exc:

                db.rollback()

                raise HTTPException(
                    status_code=400,
                    detail=f"Safety event creation failed: {str(exc)}",
                )

            except Exception as exc:

                db.rollback()

                raise HTTPException(
                    status_code=500,
                    detail=(
                        "PPE safety event integration failed: "
                        f"{str(exc)}"
                    ),
                )

        # ----------------------------------------------------
        # Return result
        # ----------------------------------------------------

        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "model": "models/best.pt",

            "ppe_analysis": result,

            "safety_events": safety_events,

            "incidents_created": incidents_created,

            "integration": {
                "safety_event_created": (
                    len(safety_events) > 0
                ),
                "incident_created": (
                    len(incidents_created) > 0
                ),
            },
        }

    except HTTPException:
        raise

    except Exception as exc:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"PPE analysis failed: {str(exc)}",
        )


# ============================================================
# SCAN HISTORY
# ============================================================

@router.get("/history")
def scan_history(
    limit: int = Query(
        50,
        ge=1,
        le=500,
        description="Maximum number of scans to return.",
    ),
    db: Session = Depends(get_db),
):

    scans = (
        db.query(Scan)
        .order_by(
            Scan.created_at.desc()
        )
        .limit(limit)
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
        .filter(
            Scan.id == scan_id
        )
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

        "target": {
            "url": scan.target_url,
            "hostname": scan.hostname,
        },

        "availability": {
            "status": scan.status,
            "status_code": scan.status_code,
            "response_time_ms": scan.response_time_ms,
            "ip_address": scan.ip_address,
        },

        "ssl": {
            "enabled": scan.ssl_enabled,
            "valid": scan.ssl_valid,
            "issuer": ssl_issuer,
            "subject": ssl_subject,
            "error": scan.ssl_error,
        },

        "security_headers": {
            "score": scan.security_headers_score,
            "total": scan.security_headers_total,
            "headers": security_headers,
            "missing": missing_headers,
            "error": scan.security_headers_error,
        },

        "risk": {
            "score": scan.risk_score,
            "risk_level": scan.risk_level,
            "findings_count": scan.findings_count,
            "severity_counts": severity_counts,
            "findings": findings,
        },

        "created_at": scan.created_at,
    }