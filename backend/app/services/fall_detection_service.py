from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.safety_event import SafetyEvent
from app.schemas.safety_event import SafetyEventCreate
from app.services.safety_service import create_safety_event
from app.services.vision_service import VisionDetection


DEFAULT_FALL_ASPECT_RATIO = 1.20
DEFAULT_MIN_FALL_WIDTH = 80.0

FALL_EVENT_COOLDOWN_SECONDS = 10

FALL_RISK_SCORES = {
    "medium": 60,
    "high": 80,
    "critical": 95,
}


def is_person(
    detection: VisionDetection,
) -> bool:
    return detection.label.lower().strip() in {
        "person",
        "worker",
        "human",
    }


def get_bounding_box(
    detection: VisionDetection,
) -> list[float] | None:
    bounding_box = detection.metadata.get(
        "bounding_box"
    )

    if not bounding_box:
        return None

    if len(bounding_box) != 4:
        return None

    return [
        float(value)
        for value in bounding_box
    ]


def calculate_box_geometry(
    bounding_box: list[float],
) -> dict:
    x1, y1, x2, y2 = bounding_box

    width = max(
        x2 - x1,
        0.0,
    )

    height = max(
        y2 - y1,
        0.0,
    )

    aspect_ratio = (
        width / height
        if height > 0
        else 0.0
    )

    center_x = (
        x1 + x2
    ) / 2

    center_y = (
        y1 + y2
    ) / 2

    return {
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "center_x": center_x,
        "center_y": center_y,
    }


def classify_fall_risk(
    width: float,
    height: float,
    aspect_ratio: float,
    fall_aspect_ratio: float,
    min_fall_width: float,
) -> tuple[bool, str, int]:
    if (
        width < min_fall_width
        or height <= 0
    ):
        return False, "low", 0

    if aspect_ratio >= (
        fall_aspect_ratio * 1.5
    ):
        return True, "critical", FALL_RISK_SCORES[
            "critical"
        ]

    if aspect_ratio >= (
        fall_aspect_ratio * 1.25
    ):
        return True, "high", FALL_RISK_SCORES[
            "high"
        ]

    if aspect_ratio >= fall_aspect_ratio:
        return True, "medium", FALL_RISK_SCORES[
            "medium"
        ]

    return False, "low", 0


def detect_fall_candidates(
    detections: list[VisionDetection],
    fall_aspect_ratio: float = DEFAULT_FALL_ASPECT_RATIO,
    min_fall_width: float = DEFAULT_MIN_FALL_WIDTH,
) -> list[dict]:
    if fall_aspect_ratio <= 0:
        fall_aspect_ratio = DEFAULT_FALL_ASPECT_RATIO

    if min_fall_width <= 0:
        min_fall_width = DEFAULT_MIN_FALL_WIDTH

    candidates = []

    for detection in detections:
        if not is_person(detection):
            continue

        bounding_box = get_bounding_box(
            detection
        )

        if bounding_box is None:
            continue

        geometry = calculate_box_geometry(
            bounding_box
        )

        is_fallen, risk_level, risk_score = (
            classify_fall_risk(
                width=geometry["width"],
                height=geometry["height"],
                aspect_ratio=geometry[
                    "aspect_ratio"
                ],
                fall_aspect_ratio=fall_aspect_ratio,
                min_fall_width=min_fall_width,
            )
        )

        candidates.append(
            {
                "event_type": "fall_detected",
                "fall_detected": is_fallen,
                "label": detection.label,
                "confidence": detection.confidence,
                "bounding_box": bounding_box,
                "width_pixels": round(
                    geometry["width"],
                    2,
                ),
                "height_pixels": round(
                    geometry["height"],
                    2,
                ),
                "aspect_ratio": round(
                    geometry["aspect_ratio"],
                    3,
                ),
                "fall_aspect_ratio": (
                    fall_aspect_ratio
                ),
                "risk_level": risk_level,
                "risk_score": risk_score,
            }
        )

    return candidates


def has_recent_fall_event(
    db: Session,
    camera_id: int | None = None,
) -> bool:
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=FALL_EVENT_COOLDOWN_SECONDS
        )
    )

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type
            == "fall_detected",
            SafetyEvent.occurred_at
            >= cutoff,
        )
    )

    if camera_id is not None:
        query = query.filter(
            SafetyEvent.camera_id
            == camera_id
        )

    return query.first() is not None


def create_fall_event(
    db: Session,
    fall_candidate: dict,
    camera_id: int | None = None,
):
    if not fall_candidate:
        return None

    if not fall_candidate.get(
        "fall_detected",
        False,
    ):
        return None

    if has_recent_fall_event(
        db=db,
        camera_id=camera_id,
    ):
        return None

    severity = str(
        fall_candidate.get(
            "risk_level",
            "high",
        )
    ).lower()

    if severity not in {
        "medium",
        "high",
        "critical",
    }:
        severity = "high"

    risk_score = int(
        fall_candidate.get(
            "risk_score",
            FALL_RISK_SCORES["high"],
        )
    )

    confidence = fall_candidate.get(
        "confidence"
    )

    width = fall_candidate.get(
        "width_pixels",
        0,
    )

    height = fall_candidate.get(
        "height_pixels",
        0,
    )

    aspect_ratio = fall_candidate.get(
        "aspect_ratio",
        0,
    )

    event_data = SafetyEventCreate(
        camera_id=camera_id,
        zone_id=None,
        event_type="fall_detected",
        severity=severity,
        title="Possible worker fall detected",
        description=(
            "A person was detected in a "
            "fall-like horizontal posture. "
            f"Bounding-box width: {width:.2f} pixels. "
            f"Height: {height:.2f} pixels. "
            f"Aspect ratio: {aspect_ratio:.3f}."
        ),
        confidence=confidence,
        detected_object="person",
        risk_score=risk_score,
        status="active",
    )

    event = create_safety_event(
        db=db,
        event_data=event_data,
    )

    return event


def process_fall_detection(
    db: Session,
    detections: list[VisionDetection],
    camera_id: int | None = None,
    fall_aspect_ratio: float = DEFAULT_FALL_ASPECT_RATIO,
    min_fall_width: float = DEFAULT_MIN_FALL_WIDTH,
) -> dict:
    candidates = detect_fall_candidates(
        detections=detections,
        fall_aspect_ratio=fall_aspect_ratio,
        min_fall_width=min_fall_width,
    )

    fallen_candidates = [
        candidate
        for candidate in candidates
        if candidate["fall_detected"]
    ]

    events_created = []

    for candidate in fallen_candidates:
        event = create_fall_event(
            db=db,
            fall_candidate=candidate,
            camera_id=camera_id,
        )

        if event is not None:
            events_created.append(event)

    return {
        "total_persons": len(candidates),
        "fall_candidates": len(
            fallen_candidates
        ),
        "events_created": len(
            events_created
        ),
        "detections": candidates,
        "safety_events": events_created,
    }