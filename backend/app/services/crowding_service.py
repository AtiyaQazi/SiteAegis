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

# Per-camera in-memory state is used for frame-level hysteresis.
#
# {
#     camera_id: {
#         "active": bool,
#         "clear_frames": int,
#     }
# }
#
# The database is the persistent source of truth for active
# crowding events.
#
# IMPORTANT:
# If the application restarts/reloads while a crowding event
# is still active in the database, create_crowding_event()
# restores the in-memory state from the database before
# processing the next frame.

_crowding_state: dict[int | None, dict[str, int | bool]] = {}

_crowding_state_lock = Lock()


# ============================================================
# DETECTION HELPERS
# ============================================================


def is_person(
    detection: VisionDetection,
) -> bool:
    """
    Return True when a vision detection represents a person.
    """

    return detection.label.lower().strip() in {
        "person",
        "worker",
        "human",
    }


def get_person_detections(
    detections: list[VisionDetection],
) -> list[VisionDetection]:
    """
    Filter the supplied detections to person/worker detections.
    """

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
    """
    Calculate crowding severity and risk score.

    Rules:

        person_count < threshold
            -> low / 0

        person_count >= threshold
            -> medium / 60

        person_count >= 1.5 * threshold
            -> high / 80

        person_count >= 2 * threshold
            -> critical / 95
    """

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
    """
    Analyze detections and determine whether crowding is present.
    """

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
    """
    Return the current in-memory crowding state for a camera.
    """

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
    Update the frame-level crowding state.

    Crowding starts immediately when detected.

    Crowding does NOT clear after one missed frame.
    It requires CROWDING_CLEAR_FRAMES consecutive
    non-crowded frames.

    Returns:

        (
            previous_active_state,
            current_active_state,
        )
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
            # A crowded frame immediately activates the state.
            state["active"] = True
            state["clear_frames"] = 0

        else:
            if bool(state["active"]):
                # Count consecutive non-crowded frames.
                state["clear_frames"] = (
                    int(state["clear_frames"]) + 1
                )

                # Only clear after the required number of
                # consecutive clear frames.
                if (
                    int(state["clear_frames"])
                    >= CROWDING_CLEAR_FRAMES
                ):
                    state["active"] = False
                    state["clear_frames"] = 0

            else:
                # No active episode exists.
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
    Explicitly reset the in-memory crowding state.

    Useful for tests and camera/live-session cleanup.

    Database events are intentionally not modified here.
    """

    with _crowding_state_lock:
        _crowding_state.pop(
            camera_id,
            None,
        )


# ============================================================
# DATABASE STATE
# ============================================================


def get_active_crowding_event(
    db: Session,
    camera_id: int | None = None,
) -> SafetyEvent | None:
    """
    Return the current active crowding event for a camera.

    The database acts as the persistent source of truth.

    This prevents duplicate events after an application
    reload/restart.
    """

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type == "crowding_detected",
            SafetyEvent.status == "active",
        )
    )

    if camera_id is None:
        query = query.filter(
            SafetyEvent.camera_id.is_(None)
        )
    else:
        query = query.filter(
            SafetyEvent.camera_id == camera_id
        )

    return (
        query
        .order_by(SafetyEvent.id.desc())
        .first()
    )


def resolve_active_crowding_event(
    db: Session,
    camera_id: int | None = None,
) -> SafetyEvent | None:
    """
    Resolve the active crowding event for a camera.

    Returns the resolved event, or None if there is no
    active crowding event.
    """

    event = get_active_crowding_event(
        db=db,
        camera_id=camera_id,
    )

    if event is None:
        return None

    event.status = "resolved"

    db.commit()
    db.refresh(event)

    return event


# ============================================================
# STATE / DATABASE SYNCHRONIZATION
# ============================================================


def restore_crowding_state_from_database(
    db: Session,
    camera_id: int | None = None,
) -> bool:
    """
    Restore the in-memory crowding state from the database.

    This is required after an application restart/reload.

    Example:

        Database:
            active crowding event exists

        Memory after restart:
            no state exists

    Without restoration, the first non-crowded frame would
    incorrectly be treated as if no crowding episode existed.

    With restoration:

        First clear frame:
            clear_frames = 1

        Second clear frame:
            clear_frames = 2
            state becomes inactive
            database event is resolved

    Returns:

        True  -> an active database event was found/restored
        False -> no active database event exists
    """

    active_event = get_active_crowding_event(
        db=db,
        camera_id=camera_id,
    )

    with _crowding_state_lock:
        state = _crowding_state.get(camera_id)

        if active_event is not None:
            # Only restore when there is no in-memory state yet.
            #
            # If state already exists, preserve its clear-frame
            # counter because it represents frames processed
            # during the current application session.
            if state is None:
                _crowding_state[camera_id] = {
                    "active": True,
                    "clear_frames": 0,
                }

            return True

        # If no database event exists and there is no active
        # in-memory state, there is nothing to restore.
        if state is None:
            return False

        return bool(state["active"])


# ============================================================
# DATABASE COMPATIBILITY HELPER
# ============================================================


def has_recent_crowding_event(
    db: Session,
    camera_id: int | None = None,
) -> bool:
    """
    Compatibility helper retained for existing callers.

    Despite the historical function name, duplicate prevention
    is now based on the active event for the camera rather than
    a time-only cooldown.
    """

    return (
        get_active_crowding_event(
            db=db,
            camera_id=camera_id,
        )
        is not None
    )


# ============================================================
# EVENT CREATION
# ============================================================


def create_crowding_event(
    db: Session,
    crowding_result: dict,
    camera_id: int | None = None,
):
    """
    Create exactly one SafetyEvent for a continuous crowding
    episode.

    The in-memory state machine handles frame-level hysteresis.

    The database active-event check prevents duplicate events
    after application reloads/restarts.

    The database state is synchronized into memory before the
    frame is processed. This guarantees that an already-active
    crowding event can be cleared correctly after a restart.
    """

    if not crowding_result:
        return None

    crowding_detected = bool(
        crowding_result.get(
            "crowding_detected",
            False,
        )
    )

    # --------------------------------------------------------
    # RESTORE PERSISTENT STATE
    # --------------------------------------------------------
    #
    # IMPORTANT:
    # Do this BEFORE update_crowding_state().
    #
    # If event #1292 is active in PostgreSQL but the backend
    # has just restarted, this restores:
    #
    #     active=True
    #     clear_frames=0
    #
    # Then the current non-crowded frame becomes clear frame #1.
    #

    restore_crowding_state_from_database(
        db=db,
        camera_id=camera_id,
    )

    # --------------------------------------------------------
    # UPDATE FRAME-LEVEL STATE
    # --------------------------------------------------------

    previous_state, current_state = (
        update_crowding_state(
            camera_id=camera_id,
            crowding_detected=crowding_detected,
        )
    )

    # --------------------------------------------------------
    # CROWD IS CURRENTLY NOT ACTIVE
    # --------------------------------------------------------

    if not current_state:

        # The state machine has just determined that the
        # crowding episode has cleared.
        #
        # Because restore_crowding_state_from_database()
        # synchronized the DB event into memory, this will
        # correctly resolve an event even after a restart.
        if previous_state:
            resolve_active_crowding_event(
                db=db,
                camera_id=camera_id,
            )

        return None

    # --------------------------------------------------------
    # PERSISTENT DUPLICATE PROTECTION
    # --------------------------------------------------------

    active_event = get_active_crowding_event(
        db=db,
        camera_id=camera_id,
    )

    if active_event is not None:
        # An active DB event already represents this ongoing
        # crowding episode.
        #
        # Do not create another SafetyEvent.
        return None

    # --------------------------------------------------------
    # FRAME-LEVEL DUPLICATE PROTECTION
    # --------------------------------------------------------

    if previous_state:
        # The in-memory state was already active, so this frame
        # belongs to the same crowding episode.
        return None

    # --------------------------------------------------------
    # BUILD NEW SAFETY EVENT
    # --------------------------------------------------------

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

    # create_safety_event() also handles the existing
    # incident-creation rules for high/critical or sufficiently
    # high-risk safety events.
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
    """
    Run crowding detection and process its SafetyEvent lifecycle.
    """

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