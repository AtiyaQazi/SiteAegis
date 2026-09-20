from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Any

from sqlalchemy.orm import Session

from app.models.safety_event import SafetyEvent
from app.schemas.safety_event import SafetyEventCreate
from app.services.safety_service import create_safety_event
from app.services.vision_service import VisionDetection


DEFAULT_MOVEMENT_THRESHOLD = 180.0
DEFAULT_CRITICAL_MOVEMENT_THRESHOLD = 320.0

UNSAFE_MOVEMENT_EVENT_COOLDOWN_SECONDS = 10

MOVEMENT_RISK_SCORES = {
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
    bounding_box = detection.metadata.get("bounding_box")

    if not bounding_box or len(bounding_box) != 4:
        return None

    return [
        float(value)
        for value in bounding_box
    ]


def get_center(
    bounding_box: list[float],
) -> tuple[float, float]:
    x1, y1, x2, y2 = bounding_box

    return (
        (x1 + x2) / 2,
        (y1 + y2) / 2,
    )


def calculate_displacement(
    previous_box: list[float],
    current_box: list[float],
) -> dict[str, float]:
    previous_x, previous_y = get_center(previous_box)
    current_x, current_y = get_center(current_box)

    delta_x = current_x - previous_x
    delta_y = current_y - previous_y

    displacement = sqrt(
        (delta_x ** 2) +
        (delta_y ** 2)
    )

    return {
        "previous_center_x": previous_x,
        "previous_center_y": previous_y,
        "current_center_x": current_x,
        "current_center_y": current_y,
        "delta_x": delta_x,
        "delta_y": delta_y,
        "displacement_pixels": displacement,
    }


def classify_movement_risk(
    displacement_pixels: float,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
    critical_movement_threshold: float = DEFAULT_CRITICAL_MOVEMENT_THRESHOLD,
) -> tuple[bool, str, int]:

    if movement_threshold <= 0:
        movement_threshold = DEFAULT_MOVEMENT_THRESHOLD

    if critical_movement_threshold <= movement_threshold:
        critical_movement_threshold = (
            DEFAULT_CRITICAL_MOVEMENT_THRESHOLD
        )

    if displacement_pixels >= critical_movement_threshold:
        return (
            True,
            "critical",
            MOVEMENT_RISK_SCORES["critical"],
        )

    if displacement_pixels >= movement_threshold * 1.5:
        return (
            True,
            "high",
            MOVEMENT_RISK_SCORES["high"],
        )

    if displacement_pixels >= movement_threshold:
        return (
            True,
            "medium",
            MOVEMENT_RISK_SCORES["medium"],
        )

    return False, "low", 0


def match_person_detections(
    previous_detections: list[VisionDetection],
    current_detections: list[VisionDetection],
) -> list[dict[str, Any]]:
    previous_persons = [
        detection
        for detection in previous_detections
        if is_person(detection)
        and get_bounding_box(detection) is not None
    ]

    current_persons = [
        detection
        for detection in current_detections
        if is_person(detection)
        and get_bounding_box(detection) is not None
    ]

    matches = []

    used_previous: set[int] = set()

    for current_index, current_detection in enumerate(
        current_persons
    ):
        current_box = get_bounding_box(
            current_detection
        )

        if current_box is None:
            continue

        current_center = get_center(current_box)

        best_index = None
        best_distance = None

        for previous_index, previous_detection in enumerate(
            previous_persons
        ):
            if previous_index in used_previous:
                continue

            previous_box = get_bounding_box(
                previous_detection
            )

            if previous_box is None:
                continue

            previous_center = get_center(
                previous_box
            )

            distance = sqrt(
                (
                    current_center[0]
                    - previous_center[0]
                ) ** 2
                +
                (
                    current_center[1]
                    - previous_center[1]
                ) ** 2
            )

            if (
                best_distance is None
                or distance < best_distance
            ):
                best_distance = distance
                best_index = previous_index

        if best_index is None:
            continue

        previous_detection = previous_persons[
            best_index
        ]

        previous_box = get_bounding_box(
            previous_detection
        )

        if previous_box is None:
            continue

        used_previous.add(best_index)

        geometry = calculate_displacement(
            previous_box=previous_box,
            current_box=current_box,
        )

        matches.append(
            {
                "previous_detection": previous_detection,
                "current_detection": current_detection,
                "previous_bounding_box": previous_box,
                "current_bounding_box": current_box,
                **geometry,
            }
        )

    return matches


def detect_unsafe_movement(
    previous_detections: list[VisionDetection],
    current_detections: list[VisionDetection],
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
    critical_movement_threshold: float = (
        DEFAULT_CRITICAL_MOVEMENT_THRESHOLD
    ),
) -> dict[str, Any]:

    matches = match_person_detections(
        previous_detections=previous_detections,
        current_detections=current_detections,
    )

    movement_results = []

    for match in matches:
        (
            unsafe,
            risk_level,
            risk_score,
        ) = classify_movement_risk(
            displacement_pixels=match[
                "displacement_pixels"
            ],
            movement_threshold=movement_threshold,
            critical_movement_threshold=(
                critical_movement_threshold
            ),
        )

        current_detection = match[
            "current_detection"
        ]

        movement_results.append(
            {
                "event_type": "unsafe_movement",
                "unsafe_movement": unsafe,
                "label": current_detection.label,
                "confidence": current_detection.confidence,
                "previous_bounding_box": match[
                    "previous_bounding_box"
                ],
                "current_bounding_box": match[
                    "current_bounding_box"
                ],
                "previous_center": [
                    round(
                        match[
                            "previous_center_x"
                        ],
                        2,
                    ),
                    round(
                        match[
                            "previous_center_y"
                        ],
                        2,
                    ),
                ],
                "current_center": [
                    round(
                        match[
                            "current_center_x"
                        ],
                        2,
                    ),
                    round(
                        match[
                            "current_center_y"
                        ],
                        2,
                    ),
                ],
                "delta_x": round(
                    match["delta_x"],
                    2,
                ),
                "delta_y": round(
                    match["delta_y"],
                    2,
                ),
                "displacement_pixels": round(
                    match[
                        "displacement_pixels"
                    ],
                    2,
                ),
                "movement_threshold": movement_threshold,
                "critical_movement_threshold": (
                    critical_movement_threshold
                ),
                "risk_level": risk_level,
                "risk_score": risk_score,
            }
        )

    unsafe_results = [
        result
        for result in movement_results
        if result["unsafe_movement"]
    ]

    return {
        "previous_persons": len([
            detection
            for detection in previous_detections
            if is_person(detection)
        ]),
        "current_persons": len([
            detection
            for detection in current_detections
            if is_person(detection)
        ]),
        "matched_persons": len(matches),
        "unsafe_movement_detected": len(
            unsafe_results
        ) > 0,
        "unsafe_movement_count": len(
            unsafe_results
        ),
        "detections": movement_results,
    }


def has_recent_unsafe_movement_event(
    db: Session,
    camera_id: int | None = None,
) -> bool:

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=UNSAFE_MOVEMENT_EVENT_COOLDOWN_SECONDS
        )
    )

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type
            == "unsafe_movement",
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


def create_unsafe_movement_event(
    db: Session,
    movement_result: dict[str, Any],
    camera_id: int | None = None,
):
    if not movement_result:
        return None

    if not movement_result.get(
        "unsafe_movement",
        False,
    ):
        return None

    if has_recent_unsafe_movement_event(
        db=db,
        camera_id=camera_id,
    ):
        return None

    severity = str(
        movement_result.get(
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
        movement_result.get(
            "risk_score",
            MOVEMENT_RISK_SCORES["high"],
        )
    )

    confidence = movement_result.get(
        "confidence"
    )

    displacement = movement_result.get(
        "displacement_pixels",
        0,
    )

    event_data = SafetyEventCreate(
        camera_id=camera_id,
        zone_id=None,
        event_type="unsafe_movement",
        severity=severity,
        title="Unsafe worker movement detected",
        description=(
            "A worker/person showed an "
            "abnormally large movement "
            "between consecutive frames. "
            f"Measured displacement: "
            f"{displacement:.2f} pixels."
        ),
        confidence=confidence,
        detected_object="person",
        risk_score=risk_score,
        status="active",
    )

    return create_safety_event(
        db=db,
        event_data=event_data,
    )


def process_unsafe_movement(
    db: Session,
    previous_detections: list[VisionDetection],
    current_detections: list[VisionDetection],
    camera_id: int | None = None,
    movement_threshold: float = DEFAULT_MOVEMENT_THRESHOLD,
    critical_movement_threshold: float = (
        DEFAULT_CRITICAL_MOVEMENT_THRESHOLD
    ),
) -> dict[str, Any]:

    detection_result = detect_unsafe_movement(
        previous_detections=previous_detections,
        current_detections=current_detections,
        movement_threshold=movement_threshold,
        critical_movement_threshold=(
            critical_movement_threshold
        ),
    )

    events_created = []

    for movement_result in detection_result[
        "detections"
    ]:
        event = create_unsafe_movement_event(
            db=db,
            movement_result=movement_result,
            camera_id=camera_id,
        )

        if event is not None:
            events_created.append(event)

    return {
        **detection_result,
        "events_created": len(
            events_created
        ),
        "safety_events": events_created,
    }