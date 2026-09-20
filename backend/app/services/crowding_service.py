from threading import Lock

from sqlalchemy.orm import Session

from app.models.safety_event import SafetyEvent
from app.schemas.safety_event import SafetyEventCreate
from app.services.safety_service import create_safety_event
from app.services.vision_service import VisionDetection


DEFAULT_CROWD_THRESHOLD = 5

# Kept for compatibility with existing imports/configuration.
CROWDING_EVENT_COOLDOWN_SECONDS = 10

# Number of consecutive non-crowded frames required before
# an active crowding condition is considered cleared.
CROWDING_CLEAR_FRAMES = 2

CROWDING_RISK_SCORES = {
    "low": 35,
    "medium": 60,
    "high": 80,
    "critical": 95,
}


# ============================================================
# CROWDING STATE
# ============================================================

# Per-camera state:
#
# {
#     camera_id: {
#         "active": bool,
#         "clear_frames": int,
#     }
# }
#
# The state is intentionally kept per camera so one camera
# cannot suppress or affect another camera's crowding events.
#
# camera_id=None is used by standalone image/API analysis.

_crowding_state: dict[int | None, dict[str, int | bool]] = {}

_crowding_state_lock = Lock()


# ============================================================
# DETECTION HELPERS
# ============================================================


def is_person(
    detection: VisionDetection,
) -> bool:
    return detection.label.lower().strip() in {
        "person",
        "worker",
        "human",
    }


def get_person_detections(
    detections: list[VisionDetection],
) -> list[VisionDetection]:
    return [
        detection
        for detection in detections
        if is_person(detection)
    ]


# ============================================================
# RISK CALCULATION
# ============================================================


def calculate_crowding_risk(
    person_count: int,
    threshold: int,
) -> tuple[str, int]:
    if threshold <= 0:
        threshold = DEFAULT_CROWD_THRESHOLD

    if person_count < threshold:
        return "low", 0

    excess_ratio = person_count / threshold

    if excess_ratio >= 2.0:
        return "critical", CROWDING_RISK_SCORES["critical"]

    if excess_ratio >= 1.5:
        return "high", CROWDING_RISK_SCORES["high"]

    return "medium", CROWDING_RISK_SCORES["medium"]


# ============================================================
# CROWDING DETECTION
# ============================================================


def detect_crowding(
    detections: list[VisionDetection],
    threshold: int = DEFAULT_CROWD_THRESHOLD,
) -> dict:
    if threshold <= 0:
        threshold = DEFAULT_CROWD_THRESHOLD

    persons = get_person_detections(detections)
    person_count = len(persons)

    risk_level, risk_score = calculate_crowding_risk(
        person_count=person_count,
        threshold=threshold,
    )

    crowding_detected = person_count >= threshold

    return {
        "event_type": "crowding_detected",
        "crowding_detected": crowding_detected,
        "person_count": person_count,
        "threshold": threshold,
        "excess_persons": max(
            person_count - threshold,
            0,
        ),
        "risk_level": risk_level,
        "risk_score": risk_score,
        "persons": [
            {
                "label": person.label,
                "confidence": person.confidence,
                "bounding_box": person.metadata.get(
                    "bounding_box"
                ),
            }
            for person in persons
        ],
    }


# ============================================================
# STATE MANAGEMENT
# ============================================================


def get_crowding_state(
    camera_id: int | None = None,
) -> bool:
    with _crowding_state_lock:
        state = _crowding_state.get(camera_id)

        if state is None:
            return False

        return bool(state["active"])


def update_crowding_state(
    camera_id: int | None,
    crowding_detected: bool,
) -> tuple[bool, bool]:
    """
    Update the crowding state.

    Crowding starts immediately when detected.

    Crowding does NOT clear after one missed frame.
    It requires CROWDING_CLEAR_FRAMES consecutive
    non-crowded frames.

    Returns:

        (previous_active_state, current_active_state)
    """

    with _crowding_state_lock:
        state = _crowding_state.setdefault(
            camera_id,
            {
                "active": False,
                "clear_frames": 0,
            },
        )

        previous_active = bool(
            state["active"]
        )

        if crowding_detected:
            state["active"] = True
            state["clear_frames"] = 0

        else:
            if bool(state["active"]):
                state["clear_frames"] = (
                    int(state["clear_frames"]) + 1
                )

                if (
                    int(state["clear_frames"])
                    >= CROWDING_CLEAR_FRAMES
                ):
                    state["active"] = False
                    state["clear_frames"] = 0
            else:
                state["clear_frames"] = 0

        current_active = bool(
            state["active"]
        )

        return (
            previous_active,
            current_active,
        )


def reset_crowding_state(
    camera_id: int | None = None,
) -> None:
    """
    Explicitly reset crowding state.

    Useful for tests and camera/live-session cleanup.
    """

    with _crowding_state_lock:
        _crowding_state.pop(
            camera_id,
            None,
        )


# ============================================================
# DATABASE COMPATIBILITY HELPER
# ============================================================


def has_recent_crowding_event(
    db: Session,
    camera_id: int | None = None,
) -> bool:
    """
    Compatibility helper retained for existing callers.

    Live duplicate prevention is handled by the state machine,
    not by a time-only cooldown.
    """

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type
            == "crowding_detected",
        )
    )

    if camera_id is not None:
        query = query.filter(
            SafetyEvent.camera_id == camera_id
        )

    return query.first() is not None


# ============================================================
# EVENT CREATION
# ============================================================


def create_crowding_event(
    db: Session,
    crowding_result: dict,
    camera_id: int | None = None,
):
    if not crowding_result:
        return None

    crowding_detected = bool(
        crowding_result.get(
            "crowding_detected",
            False,
        )
    )

    previous_state, current_state = (
        update_crowding_state(
            camera_id=camera_id,
            crowding_detected=crowding_detected,
        )
    )

    # No active crowding condition.
    if not current_state:
        return None

    # Already crowded on the previous frame/request.
    # Detection is still returned to the caller, but another
    # database event is not created.
    if previous_state:
        return None

    person_count = int(
        crowding_result.get(
            "person_count",
            0,
        )
    )

    threshold = int(
        crowding_result.get(
            "threshold",
            DEFAULT_CROWD_THRESHOLD,
        )
    )

    severity = str(
        crowding_result.get(
            "risk_level",
            "medium",
        )
    ).lower()

    if severity not in {
        "low",
        "medium",
        "high",
        "critical",
    }:
        severity = "medium"

    risk_score = int(
        crowding_result.get(
            "risk_score",
            CROWDING_RISK_SCORES["medium"],
        )
    )

    confidence_values = [
        person.get("confidence")
        for person in crowding_result.get(
            "persons",
            [],
        )
        if person.get("confidence") is not None
    ]

    confidence = (
        min(confidence_values)
        if confidence_values
        else None
    )

    event_data = SafetyEventCreate(
        camera_id=camera_id,
        zone_id=None,
        event_type="crowding_detected",
        severity=severity,
        title="Crowding detected",
        description=(
            f"{person_count} persons detected in the "
            f"monitored area. "
            f"Configured crowd threshold: {threshold}. "
            f"Excess persons: "
            f"{max(person_count - threshold, 0)}."
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


# ============================================================
# MAIN PROCESSING
# ============================================================


def process_crowding(
    db: Session,
    detections: list[VisionDetection],
    camera_id: int | None = None,
    threshold: int = DEFAULT_CROWD_THRESHOLD,
) -> dict:
    crowding_result = detect_crowding(
        detections=detections,
        threshold=threshold,
    )

    event = create_crowding_event(
        db=db,
        crowding_result=crowding_result,
        camera_id=camera_id,
    )

    return {
        "crowding": crowding_result,
        "event_created": event is not None,
        "safety_event": event,
    }