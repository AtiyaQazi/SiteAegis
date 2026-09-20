from datetime import datetime, timedelta, timezone
from math import sqrt

from sqlalchemy.orm import Session

from app.schemas.safety_event import SafetyEventCreate
from app.models.safety_event import SafetyEvent
from app.services.safety_service import create_safety_event
from app.services.vision_service import VisionDetection


# ============================================================
# CONFIGURATION
# ============================================================

DEFAULT_PROXIMITY_THRESHOLD = 120.0

PROXIMITY_EVENT_COOLDOWN_SECONDS = 10

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

    return [
        float(value)
        for value in bounding_box
    ]


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

    return normalized_label in {
        normalize_detection_label(label)
        for label in MACHINE_LABELS
    }


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
    Create a stable-enough relationship key from the
    worker and machine labels plus their bounding boxes.

    This allows cooldown to apply to the same spatial
    worker-machine relationship without suppressing
    separate workers or machines.

    The coordinates are rounded to reduce tiny frame-to-frame
    detection changes from creating a completely new key.
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
# DATABASE COOLDOWN
# ============================================================

def has_recent_proximity_event(
    db: Session,
    proximity_event: dict,
    camera_id: int | None = None,
) -> bool:
    """
    Prevent repeated events for the same worker-machine
    spatial relationship during the cooldown period.

    Unlike the previous camera-wide cooldown, this does
    not suppress a different worker or different machine.
    """

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(
            seconds=PROXIMITY_EVENT_COOLDOWN_SECONDS
        )
    )

    query = (
        db.query(SafetyEvent)
        .filter(
            SafetyEvent.event_type
            == "worker_machine_proximity",
            SafetyEvent.occurred_at >= cutoff,
        )
    )

    if camera_id is not None:
        query = query.filter(
            SafetyEvent.camera_id == camera_id
        )

    recent_events = query.all()

    current_key = create_proximity_relationship_key(
        proximity_event
    )

    for event in recent_events:
        description = event.description or ""

        worker_label = "person"
        machine_label = event.detected_object or "machine"

        worker_marker = f"Worker: {worker_label}."
        machine_marker = f"Machine: {machine_label}."

        if (
            worker_marker not in description
            or machine_marker not in description
        ):
            continue

        event_box_gap = None
        event_threshold = None
        event_center_distance = None

        try:
            for part in description.split("."):
                part = part.strip()

                if part.startswith(
                    "Bounding-box gap:"
                ):
                    event_box_gap = float(
                        part.split(":")[1]
                        .replace(
                            "pixels",
                            "",
                        )
                        .strip()
                    )

                elif part.startswith(
                    "Allowed threshold:"
                ):
                    event_threshold = float(
                        part.split(":")[1]
                        .replace(
                            "pixels",
                            "",
                        )
                        .strip()
                    )

                elif part.startswith(
                    "Center distance:"
                ):
                    event_center_distance = float(
                        part.split(":")[1]
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
            continue

        if (
            event_box_gap is None
            or event_threshold is None
            or event_center_distance is None
        ):
            continue

        current_worker = (
            proximity_event.get(
                "worker",
                {},
            )
        )

        current_machine = (
            proximity_event.get(
                "machine",
                {},
            )
        )

        current_worker_box = current_worker.get(
            "bounding_box",
            [],
        )

        current_machine_box = current_machine.get(
            "bounding_box",
            [],
        )

        if (
            not current_worker_box
            or not current_machine_box
        ):
            continue

        current_box_gap = proximity_event.get(
            "box_gap_pixels",
            0,
        )

        current_center_distance = proximity_event.get(
            "distance_pixels",
            0,
        )

        # Spatial tolerance keeps the same detected
        # worker-machine pair grouped across nearby frames.
        box_gap_matches = abs(
            float(event_box_gap)
            - float(current_box_gap)
        ) <= 35.0

        center_distance_matches = abs(
            float(event_center_distance)
            - float(current_center_distance)
        ) <= 50.0

        threshold_matches = abs(
            float(event_threshold)
            - float(
                proximity_event.get(
                    "threshold_pixels",
                    DEFAULT_PROXIMITY_THRESHOLD,
                )
            )
        ) <= 1.0

        if (
            box_gap_matches
            and center_distance_matches
            and threshold_matches
        ):
            return True

    return False


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

    Cooldown is applied to the individual worker-machine
    relationship rather than the entire camera.
    """

    if not proximity_event:
        return None

    if proximity_event.get("event_type") != (
        "worker_machine_proximity"
    ):
        return None

    if has_recent_proximity_event(
        db=db,
        proximity_event=proximity_event,
        camera_id=camera_id,
    ):
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

    box_gap = proximity_event.get(
        "box_gap_pixels",
        0,
    )

    threshold = proximity_event.get(
        "threshold_pixels",
        DEFAULT_PROXIMITY_THRESHOLD,
    )

    center_distance = proximity_event.get(
        "distance_pixels",
        0,
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
            f"Bounding-box gap: {box_gap:.2f} pixels. "
            f"Allowed threshold: {threshold:.2f} pixels. "
            f"Center distance: "
            f"{center_distance:.2f} pixels."
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
    3. Create SafetyEvent for each independent
       worker-machine relationship.
    4. Suppress repeated events for the same relationship
       during the cooldown period.
    5. Existing safety service automatically creates
       an Incident when risk is high/critical.
    """

    proximity_events = (
        detect_worker_machine_proximity(
            detections=detections,
            threshold=threshold,
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
        "worker_count": worker_count,
        "machine_count": machine_count,
        "proximity_events": len(
            proximity_events
        ),
        "proximity_detections": proximity_events,
        "safety_events": events_created,
    }