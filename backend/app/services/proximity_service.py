from datetime import datetime, timezone
from math import sqrt

from sqlalchemy.orm import Session

from app.models.safety_event import SafetyEvent
from app.schemas.safety_event import SafetyEventCreate
from app.services.safety_service import create_safety_event
from app.services.vision_service import VisionDetection


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_PROXIMITY_THRESHOLD = 120.0

# Spatial tolerances used to determine whether a proximity
# relationship in the current frame represents the same
# active relationship already stored in the database.
PROXIMITY_BOX_GAP_TOLERANCE = 35.0
PROXIMITY_CENTER_DISTANCE_TOLERANCE = 50.0
PROXIMITY_THRESHOLD_TOLERANCE = 1.0

MACHINE_LABELS = {
    # COCO / general object classes
    "truck",
    "car",
    "bus",
    "train",
    "motorcycle",
    "bicycle",
    "boat",

    # Construction machine classes
    "forklift",
    "excavator",
    "excavators",
    "crane",
    "loader",
    "wheel_loader",
    "wheel loader",
    "dump_truck",
    "dump truck",
    "bulldozer",
    "tractor",
    "machine",
}

PROXIMITY_RISK_SCORES = {
    "low": 35,
    "medium": 60,
    "high": 80,
    "critical": 95,
}


# ============================================================
# LABEL NORMALIZATION
# ============================================================

def normalize_detection_label(
    label: str | None,
) -> str:
    """
    Normalize an AI detection label so model-specific
    naming variations can be matched consistently.
    """

    normalized = (
        label or ""
    ).strip().lower()

    normalized = normalized.replace(
        "-",
        "_",
    )

    normalized = normalized.replace(
        " ",
        "_",
    )

    aliases = {
        "excavators": "excavator",
        "wheel_loaders": "wheel_loader",
        "dump_trucks": "dump_truck",
    }

    return aliases.get(
        normalized,
        normalized,
    )


# ============================================================
# GEOMETRY
# ============================================================

def get_bounding_box(
    detection: VisionDetection,
) -> list[float] | None:
    """
    Return [x1, y1, x2, y2] from a detection.
    """

    bounding_box = detection.metadata.get(
        "bounding_box"
    )

    if not bounding_box:
        return None

    if len(bounding_box) != 4:
        return None

    try:
        return [
            float(value)
            for value in bounding_box
        ]
    except (
        TypeError,
        ValueError,
    ):
        return None


def get_center(
    bounding_box: list[float],
) -> tuple[float, float]:
    """
    Calculate bounding-box center.
    """

    x1, y1, x2, y2 = bounding_box

    return (
        (x1 + x2) / 2,
        (y1 + y2) / 2,
    )


def calculate_center_distance(
    box_a: list[float],
    box_b: list[float],
) -> float:
    """
    Calculate Euclidean distance between two
    bounding-box centers.
    """

    center_a = get_center(box_a)
    center_b = get_center(box_b)

    dx = center_a[0] - center_b[0]
    dy = center_a[1] - center_b[1]

    return sqrt(
        dx * dx + dy * dy
    )


def calculate_box_gap(
    box_a: list[float],
    box_b: list[float],
) -> float:
    """
    Calculate the shortest pixel gap between two
    bounding boxes.

    Returns 0 when boxes overlap.
    """

    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b

    horizontal_gap = max(
        bx1 - ax2,
        ax1 - bx2,
        0.0,
    )

    vertical_gap = max(
        by1 - ay2,
        ay1 - by2,
        0.0,
    )

    return sqrt(
        horizontal_gap * horizontal_gap
        + vertical_gap * vertical_gap
    )


# ============================================================
# CLASSIFICATION
# ============================================================

def is_person(
    detection: VisionDetection,
) -> bool:
    """
    Determine whether a detection represents a person.
    """

    return normalize_detection_label(
        detection.label
    ) in {
        "person",
        "worker",
        "human",
    }


def is_machine(
    detection: VisionDetection,
) -> bool:
    """
    Determine whether a detection represents
    construction equipment or another vehicle.
    """

    normalized_label = normalize_detection_label(
        detection.label
    )

    normalized_machine_labels = {
        normalize_detection_label(label)
        for label in MACHINE_LABELS
    }

    return normalized_label in normalized_machine_labels


# ============================================================
# PROXIMITY DETECTION
# ============================================================

def detect_worker_machine_proximity(
    detections: list[VisionDetection],
    threshold: float = DEFAULT_PROXIMITY_THRESHOLD,
) -> list[dict]:
    """
    Detect workers who are too close to machines.

    Distance is measured using the shortest gap between
    bounding boxes rather than only center distance.
    """

    if threshold <= 0:
        threshold = DEFAULT_PROXIMITY_THRESHOLD

    persons = [
        detection
        for detection in detections
        if is_person(detection)
    ]

    machines = [
        detection
        for detection in detections
        if is_machine(detection)
    ]

    proximity_events = []

    for person in persons:
        person_box = get_bounding_box(
            person
        )

        if person_box is None:
            continue

        for machine in machines:
            machine_box = get_bounding_box(
                machine
            )

            if machine_box is None:
                continue

            center_distance = calculate_center_distance(
                person_box,
                machine_box,
            )

            box_gap = calculate_box_gap(
                person_box,
                machine_box,
            )

            if box_gap > threshold:
                continue

            if box_gap <= threshold * 0.25:
                risk_level = "critical"
                risk_score = PROXIMITY_RISK_SCORES[
                    "critical"
                ]

            elif box_gap <= threshold * 0.50:
                risk_level = "high"
                risk_score = PROXIMITY_RISK_SCORES[
                    "high"
                ]

            elif box_gap <= threshold * 0.75:
                risk_level = "medium"
                risk_score = PROXIMITY_RISK_SCORES[
                    "medium"
                ]

            else:
                risk_level = "low"
                risk_score = PROXIMITY_RISK_SCORES[
                    "low"
                ]

            proximity_events.append(
                {
                    "event_type": (
                        "worker_machine_proximity"
                    ),
                    "worker": {
                        "label": person.label,
                        "confidence": person.confidence,
                        "bounding_box": person_box,
                    },
                    "machine": {
                        "label": machine.label,
                        "confidence": machine.confidence,
                        "bounding_box": machine_box,
                    },
                    "distance_pixels": round(
                        center_distance,
                        2,
                    ),
                    "box_gap_pixels": round(
                        box_gap,
                        2,
                    ),
                    "threshold_pixels": threshold,
                    "risk_level": risk_level,
                    "risk_score": risk_score,
                }
            )

    return proximity_events


# ============================================================
# RELATIONSHIP KEY
# ============================================================

def create_proximity_relationship_key(
    proximity_event: dict,
) -> str:
    """
    Create a stable spatial relationship key.

    Bounding-box coordinates are rounded to 25-pixel buckets
    so small frame-to-frame detection changes do not create
    a new logical relationship.
    """

    worker = proximity_event.get(
        "worker",
        {},
    )

    machine = proximity_event.get(
        "machine",
        {},
    )

    worker_box = worker.get(
        "bounding_box",
        [],
    )

    machine_box = machine.get(
        "bounding_box",
        [],
    )

    worker_label = normalize_detection_label(
        worker.get(
            "label",
            "person",
        )
    )

    machine_label = normalize_detection_label(
        machine.get(
            "label",
            "machine",
        )
    )

    rounded_worker_box = tuple(
        round(float(value) / 25) * 25
        for value in worker_box
    )

    rounded_machine_box = tuple(
        round(float(value) / 25) * 25
        for value in machine_box
    )

    return (
        f"{worker_label}:"
        f"{rounded_worker_box}:"
        f"{machine_label}:"
        f"{rounded_machine_box}"
    )


# ============================================================
# DATABASE RELATIONSHIP MATCHING
# ============================================================

def _parse_event_geometry(
    event: SafetyEvent,
) -> dict | None:
    """
    Extract persisted proximity geometry from an existing
    SafetyEvent description.
    """

    description = event.description or ""

    worker_label = None
    machine_label = None
    box_gap = None
    threshold = None
    center_distance = None

    for raw_part in description.split("."):
        part = raw_part.strip()

        if part.startswith("Worker:"):
            worker_label = part.split(
                ":",
                1,
            )[1].strip()

        elif part.startswith("Machine:"):
            machine_label = part.split(
                ":",
                1,
            )[1].strip()

        elif part.startswith(
            "Bounding-box gap:"
        ):
            try:
                box_gap = float(
                    part.split(
                        ":",
                        1,
                    )[1]
                    .replace(
                        "pixels",
                        "",
                    )
                    .strip()
                )
            except (
                ValueError,
                IndexError,
            ):
                pass

        elif part.startswith(
            "Allowed threshold:"
        ):
            try:
                threshold = float(
                    part.split(
                        ":",
                        1,
                    )[1]
                    .replace(
                        "pixels",
                        "",
                    )
                    .strip()
                )
            except (
                ValueError,
                IndexError,
            ):
                pass

        elif part.startswith(
            "Center distance:"
        ):
            try:
                center_distance = float(
                    part.split(
                        ":",
                        1,
                    )[1]
                    .replace(
                        "pixels",
                        "",
                    )
                    .strip()
                )
            except (
                ValueError,
                IndexError,
            ):
                pass

    if (
        worker_label is None
        or machine_label is None
        or box_gap is None
        or threshold is None
        or center_distance is None
    ):
        return None

    return {
        "worker_label": worker_label,
        "machine_label": machine_label,
        "box_gap": box_gap,
        "threshold": threshold,
        "center_distance": center_distance,
    }


def _proximity_relationship_matches(
    event: SafetyEvent,
    proximity_event: dict,
) -> bool:
    """
    Determine whether a persisted SafetyEvent represents
    the same worker-machine relationship as the current
    detection.
    """

    persisted = _parse_event_geometry(
        event
    )

    if persisted is None:
        return False

    worker = proximity_event.get(
        "worker",
        {},
    )

    machine = proximity_event.get(
        "machine",
        {},
    )

    current_worker_label = worker.get(
        "label",
        "person",
    )

    current_machine_label = machine.get(
        "label",
        "machine",
    )

    current_worker_normalized = (
        normalize_detection_label(
            current_worker_label
        )
    )

    current_machine_normalized = (
        normalize_detection_label(
            current_machine_label
        )
    )

    persisted_worker_normalized = (
        normalize_detection_label(
            persisted["worker_label"]
        )
    )

    persisted_machine_normalized = (
        normalize_detection_label(
            persisted["machine_label"]
        )
    )

    if (
        persisted_worker_normalized
        != current_worker_normalized
    ):
        return False

    if (
        persisted_machine_normalized
        != current_machine_normalized
    ):
        return False

    current_box_gap = float(
        proximity_event.get(
            "box_gap_pixels",
            0,
        )
    )

    current_center_distance = float(
        proximity_event.get(
            "distance_pixels",
            0,
        )
    )

    current_threshold = float(
        proximity_event.get(
            "threshold_pixels",
            DEFAULT_PROXIMITY_THRESHOLD,
        )
    )

    if abs(
        persisted["box_gap"]
        - current_box_gap
    ) > PROXIMITY_BOX_GAP_TOLERANCE:
        return False

    if abs(
        persisted["center_distance"]
        - current_center_distance
    ) > PROXIMITY_CENTER_DISTANCE_TOLERANCE:
        return False

    if abs(
        persisted["threshold"]
        - current_threshold
    ) > PROXIMITY_THRESHOLD_TOLERANCE:
        return False

    return True


def get_active_proximity_events(
    db: Session,
    camera_id: int | None = None,
) -> list[SafetyEvent]:
    """
    Retrieve currently active worker-machine proximity
    events from the database.

    The database is the persistent source of truth, so this
    continues to work after a Python-process restart.
    """

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type
            == "worker_machine_proximity",
            SafetyEvent.status == "active",
        )
    )

    if camera_id is not None:
        query = query.filter(
            SafetyEvent.camera_id == camera_id
        )

    return query.order_by(
        SafetyEvent.id.asc()
    ).all()


def find_matching_active_proximity_event(
    db: Session,
    proximity_event: dict,
    camera_id: int | None = None,
) -> SafetyEvent | None:
    """
    Find the persisted active SafetyEvent representing
    the same worker-machine relationship.
    """

    active_events = get_active_proximity_events(
        db=db,
        camera_id=camera_id,
    )

    for event in active_events:
        if _proximity_relationship_matches(
            event=event,
            proximity_event=proximity_event,
        ):
            return event

    return None


# ============================================================
# BACKWARD-COMPATIBLE DUPLICATE CHECK
# ============================================================

def has_recent_proximity_event(
    db: Session,
    proximity_event: dict,
    camera_id: int | None = None,
) -> bool:
    """
    Backward-compatible helper.

    Proximity deduplication is now based on active-event
    lifecycle rather than a time-based cooldown.
    """

    return (
        find_matching_active_proximity_event(
            db=db,
            proximity_event=proximity_event,
            camera_id=camera_id,
        )
        is not None
    )


# ============================================================
# ACTIVE EVENT RESOLUTION
# ============================================================

def resolve_active_proximity_event(
    db: Session,
    event: SafetyEvent,
) -> SafetyEvent:
    """
    Resolve an active proximity event when the corresponding
    worker-machine relationship is no longer detected.
    """

    event.status = "resolved"
    db.add(event)

    return event


def resolve_missing_proximity_events(
    db: Session,
    current_proximity_events: list[dict],
    camera_id: int | None = None,
) -> int:
    """
    Resolve active proximity events whose relationships are
    absent from the current frame.

    This gives proximity detection an explicit lifecycle:

        active -> resolved

    A later reappearance creates a new SafetyEvent.
    """

    active_events = get_active_proximity_events(
        db=db,
        camera_id=camera_id,
    )

    resolved_count = 0

    for active_event in active_events:
        still_present = False

        for current_event in current_proximity_events:
            if _proximity_relationship_matches(
                event=active_event,
                proximity_event=current_event,
            ):
                still_present = True
                break

        if not still_present:
            resolve_active_proximity_event(
                db=db,
                event=active_event,
            )
            resolved_count += 1

    if resolved_count:
        db.commit()

    return resolved_count


# ============================================================
# SAFETY EVENT CREATION
# ============================================================

def create_worker_machine_proximity_event(
    db: Session,
    proximity_event: dict,
    camera_id: int | None = None,
):
    """
    Convert a proximity detection into a SafetyEvent.

    A new event is created only when the same relationship
    does not already have an active database event.
    """

    if not proximity_event:
        return None

    if proximity_event.get("event_type") != (
        "worker_machine_proximity"
    ):
        return None

    existing_event = (
        find_matching_active_proximity_event(
            db=db,
            proximity_event=proximity_event,
            camera_id=camera_id,
        )
    )

    if existing_event is not None:
        return None

    worker = proximity_event.get(
        "worker",
        {},
    )

    machine = proximity_event.get(
        "machine",
        {},
    )

    worker_label = worker.get(
        "label",
        "person",
    )

    machine_label = machine.get(
        "label",
        "machine",
    )

    worker_confidence = worker.get(
        "confidence"
    )

    machine_confidence = machine.get(
        "confidence"
    )

    confidence_values = [
        value
        for value in (
            worker_confidence,
            machine_confidence,
        )
        if value is not None
    ]

    if confidence_values:
        confidence = min(
            confidence_values
        )
    else:
        confidence = None

    severity = str(
        proximity_event.get(
            "risk_level",
            "high",
        )
    ).lower()

    if severity not in {
        "low",
        "medium",
        "high",
        "critical",
    }:
        severity = "high"

    risk_score = int(
        proximity_event.get(
            "risk_score",
            PROXIMITY_RISK_SCORES["high"],
        )
    )

    box_gap = float(
        proximity_event.get(
            "box_gap_pixels",
            0,
        )
    )

    threshold = float(
        proximity_event.get(
            "threshold_pixels",
            DEFAULT_PROXIMITY_THRESHOLD,
        )
    )

    center_distance = float(
        proximity_event.get(
            "distance_pixels",
            0,
        )
    )

    relationship_key = (
        create_proximity_relationship_key(
            proximity_event
        )
    )

    event_data = SafetyEventCreate(
        camera_id=camera_id,
        zone_id=None,
        event_type="worker_machine_proximity",
        severity=severity,
        title="Worker too close to machine",
        description=(
            f"Worker detected too close to "
            f"{machine_label}. "
            f"Worker: {worker_label}. "
            f"Machine: {machine_label}. "
            f"Bounding-box gap: "
            f"{box_gap:.2f} pixels. "
            f"Allowed threshold: "
            f"{threshold:.2f} pixels. "
            f"Center distance: "
            f"{center_distance:.2f} pixels. "
            f"Relationship key: "
            f"{relationship_key}."
        ),
        confidence=confidence,
        detected_object=machine_label,
        risk_score=risk_score,
        status="active",
    )

    event = create_safety_event(
        db=db,
        event_data=event_data,
    )

    return event


# ============================================================
# FULL PROXIMITY PIPELINE
# ============================================================

def process_worker_machine_proximity(
    db: Session,
    detections: list[VisionDetection],
    camera_id: int | None = None,
    threshold: float = DEFAULT_PROXIMITY_THRESHOLD,
) -> dict:
    """
    Complete worker-machine proximity pipeline.

    1. Detect workers and machines.
    2. Calculate bounding-box proximity.
    3. Resolve relationships no longer present.
    4. Create SafetyEvent for new relationships.
    5. Keep existing relationships active without duplicates.
    6. Use the database as persistent lifecycle state.
    """

    proximity_events = (
        detect_worker_machine_proximity(
            detections=detections,
            threshold=threshold,
        )
    )

    resolved_count = (
        resolve_missing_proximity_events(
            db=db,
            current_proximity_events=proximity_events,
            camera_id=camera_id,
        )
    )

    events_created = []

    for proximity_event in proximity_events:
        event = (
            create_worker_machine_proximity_event(
                db=db,
                proximity_event=proximity_event,
                camera_id=camera_id,
            )
        )

        if event is not None:
            events_created.append(event)

    worker_count = sum(
        1
        for detection in detections
        if is_person(detection)
    )

    machine_count = sum(
        1
        for detection in detections
        if is_machine(detection)
    )

    return {
        "total_proximity_detections": len(
            proximity_events
        ),
        "events_created": len(
            events_created
        ),
        "events_resolved": resolved_count,
        "worker_count": worker_count,
        "machine_count": machine_count,
        "proximity_events": len(
            proximity_events
        ),
        "proximity_detections": proximity_events,
        "safety_events": events_created,
    }
