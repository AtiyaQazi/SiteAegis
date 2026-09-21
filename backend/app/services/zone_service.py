from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.safety_event import SafetyEvent
from app.models.zone import Zone
from app.models.zone_presence import ZonePresence
from app.services.incident_service import create_incident_from_event


# ============================================================
# TIME
# ============================================================

def utc_now() -> datetime:
    """
    Return current UTC time as a naive datetime.

    SiteAegis stores DateTime values without timezone
    information, so comparisons use naive UTC.
    """

    return datetime.now(
        timezone.utc
    ).replace(
        tzinfo=None
    )


# ============================================================
# COORDINATE / POLYGON HELPERS
# ============================================================

def normalize_point(
    point: Any,
) -> tuple[float, float] | None:
    """
    Convert a point into an (x, y) tuple.

    Supported formats:

        [x, y]
        (x, y)
        {"x": x, "y": y}
        {"X": x, "Y": y}
    """

    if point is None:
        return None

    if isinstance(
        point,
        (list, tuple),
    ):

        if len(point) < 2:
            return None

        try:
            return (
                float(point[0]),
                float(point[1]),
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    if isinstance(
        point,
        dict,
    ):

        x = point.get(
            "x",
            point.get(
                "X"
            ),
        )

        y = point.get(
            "y",
            point.get(
                "Y"
            ),
        )

        if x is None or y is None:
            return None

        try:
            return (
                float(x),
                float(y),
            )
        except (
            TypeError,
            ValueError,
        ):
            return None

    return None


def normalize_polygon(
    polygon: Any,
) -> list[tuple[float, float]]:
    """
    Normalize a zone polygon into a list of (x, y) points.
    """

    if not polygon:
        return []

    normalized = []

    for point in polygon:

        normalized_point = normalize_point(
            point
        )

        if normalized_point is not None:
            normalized.append(
                normalized_point
            )

    return normalized


def point_inside_polygon(
    x: float,
    y: float,
    polygon: list[tuple[float, float]],
) -> bool:
    """
    Determine whether a point is inside a polygon
    using the standard ray-casting algorithm.
    """

    if len(polygon) < 3:
        return False

    inside = False

    previous_x, previous_y = polygon[-1]

    for current_x, current_y in polygon:

        intersects = (
            (
                current_y > y
            )
            !=
            (
                previous_y > y
            )
        )

        if intersects:

            denominator = (
                previous_y
                - current_y
            )

            if denominator == 0:
                denominator = 1e-12

            intersection_x = (
                (
                    previous_x
                    - current_x
                )
                * (
                    y
                    - current_y
                )
                / denominator
            ) + current_x

            if x < intersection_x:
                inside = not inside

        previous_x = current_x
        previous_y = current_y

    return inside


# ============================================================
# DETECTION VALUE / METADATA HELPERS
# ============================================================

def get_detection_value(
    detection: Any,
    *names: str,
) -> Any:
    """
    Read a value from either a VisionDetection object
    or a dictionary.
    """

    if detection is None:
        return None

    if isinstance(
        detection,
        dict,
    ):

        for name in names:

            if name in detection:
                return detection[name]

        return None

    for name in names:

        if hasattr(
            detection,
            name,
        ):

            return getattr(
                detection,
                name,
            )

    return None


def get_detection_metadata(
    detection: Any,
) -> dict[str, Any]:
    """
    Return detection metadata when available.

    VisionDetection objects used by SiteAegis store
    bounding-box information inside:

        detection.metadata["bounding_box"]
    """

    if detection is None:
        return {}

    if isinstance(
        detection,
        dict,
    ):

        metadata = detection.get(
            "metadata"
        )

    else:

        metadata = getattr(
            detection,
            "metadata",
            None,
        )

    if isinstance(
        metadata,
        dict,
    ):

        return metadata

    return {}


# ============================================================
# DETECTION BOUNDING BOX
# ============================================================

def get_detection_bbox(
    detection: Any,
) -> tuple[
    float,
    float,
    float,
    float,
] | None:
    """
    Extract bounding-box coordinates.

    Supported formats:

        x1, y1, x2, y2

        bbox = [x1, y1, x2, y2]

        bounding_box = [x1, y1, x2, y2]

        metadata = {
            "bounding_box": [x1, y1, x2, y2]
        }

    The last format is the one currently produced
    by SiteAegis VisionDetection.
    """

    # --------------------------------------------------------
    # 1. Direct bbox fields
    # --------------------------------------------------------

    bbox = get_detection_value(
        detection,
        "bbox",
        "box",
        "bounding_box",
    )

    # --------------------------------------------------------
    # 2. Metadata bbox
    # --------------------------------------------------------

    if bbox is None:

        metadata = get_detection_metadata(
            detection
        )

        bbox = (
            metadata.get(
                "bounding_box"
            )
            or metadata.get(
                "bbox"
            )
            or metadata.get(
                "box"
            )
        )

    # --------------------------------------------------------
    # 3. Parse bbox dictionary/list
    # --------------------------------------------------------

    if bbox is not None:

        if isinstance(
            bbox,
            dict,
        ):

            x1 = bbox.get(
                "x1",
                bbox.get(
                    "left"
                ),
            )

            y1 = bbox.get(
                "y1",
                bbox.get(
                    "top"
                ),
            )

            x2 = bbox.get(
                "x2",
                bbox.get(
                    "right"
                ),
            )

            y2 = bbox.get(
                "y2",
                bbox.get(
                    "bottom"
                ),
            )

            values = (
                x1,
                y1,
                x2,
                y2,
            )

        elif isinstance(
            bbox,
            (list, tuple),
        ):

            if len(bbox) < 4:
                values = None

            else:
                values = (
                    bbox[0],
                    bbox[1],
                    bbox[2],
                    bbox[3],
                )

        else:

            values = None

        if values is not None:

            try:

                return (
                    float(values[0]),
                    float(values[1]),
                    float(values[2]),
                    float(values[3]),
                )

            except (
                TypeError,
                ValueError,
            ):

                pass

    # --------------------------------------------------------
    # 4. Individual direct coordinates
    # --------------------------------------------------------

    x1 = get_detection_value(
        detection,
        "x1",
        "left",
    )

    y1 = get_detection_value(
        detection,
        "y1",
        "top",
    )

    x2 = get_detection_value(
        detection,
        "x2",
        "right",
    )

    y2 = get_detection_value(
        detection,
        "y2",
        "bottom",
    )

    if (
        x1 is None
        or y1 is None
        or x2 is None
        or y2 is None
    ):

        return None

    try:

        return (
            float(x1),
            float(y1),
            float(x2),
            float(y2),
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# DETECTION CENTER
# ============================================================

def get_detection_center(
    detection: Any,
) -> tuple[
    float,
    float,
] | None:
    """
    Return the center point of a detection bounding box.
    """

    bbox = get_detection_bbox(
        detection
    )

    if bbox is None:
        return None

    x1, y1, x2, y2 = bbox

    return (
        (
            x1 + x2
        ) / 2.0,
        (
            y1 + y2
        ) / 2.0,
    )


# ============================================================
# DETECTION FEET POINT
# ============================================================

def get_detection_feet_point(
    detection: Any,
) -> tuple[
    float,
    float,
] | None:
    """
    Return the bottom-center point of a person's
    bounding box.

    For construction-site restricted zones, the feet
    point is more appropriate than the bounding-box
    center because it represents where the person is
    physically standing.
    """

    bbox = get_detection_bbox(
        detection
    )

    if bbox is None:
        return None

    x1, _, x2, y2 = bbox

    feet_x = (
        x1 + x2
    ) / 2.0

    feet_y = y2

    return (
        feet_x,
        feet_y,
    )


# ============================================================
# PERSON DETECTION
# ============================================================

def is_person_detection(
    detection: Any,
) -> bool:
    """
    Determine whether a detection represents a person.
    """

    label = get_detection_value(
        detection,
        "label",
        "class_name",
        "class_label",
        "name",
        "detected_object",
    )

    if label is None:
        return False

    normalized_label = str(
        label
    ).strip().lower()

    return normalized_label in {
        "person",
        "worker",
        "human",
    }


def detect_persons_in_zone(
    zone: Zone,
    detections: list[Any],
    image_width: int,
    image_height: int,
) -> list[Any]:
    """
    Return detected persons whose FEET POINT lies
    inside the configured restricted-zone polygon.

    Zone polygons may use:

        normalized coordinates:
            0.0 -> 1.0

    or:

        pixel coordinates:
            0 -> image_width / image_height
    """

    if not zone.polygon:
        return []

    polygon = normalize_polygon(
        zone.polygon
    )

    if len(polygon) < 3:
        return []

    if (
        image_width <= 0
        or image_height <= 0
    ):
        return []

    # --------------------------------------------------------
    # Determine whether polygon is normalized.
    # --------------------------------------------------------

    normalized_polygon = all(
        0.0 <= x <= 1.0
        and
        0.0 <= y <= 1.0
        for x, y in polygon
    )

    if normalized_polygon:

        polygon_pixels = [
            (
                x * image_width,
                y * image_height,
            )
            for x, y in polygon
        ]

    else:

        polygon_pixels = polygon

    # --------------------------------------------------------
    # Check every detected person.
    # --------------------------------------------------------

    persons_in_zone = []

    for detection in detections:

        if not is_person_detection(
            detection
        ):
            continue

        feet_point = get_detection_feet_point(
            detection
        )

        if feet_point is None:
            continue

        feet_x, feet_y = feet_point

        if point_inside_polygon(
            feet_x,
            feet_y,
            polygon_pixels,
        ):

            persons_in_zone.append(
                detection
            )

    return persons_in_zone


# ============================================================
# ZONE PRESENCE
# ============================================================

def get_zone_presence(
    db: Session,
    zone_id: int,
    camera_id: int | None = None,
) -> ZonePresence | None:
    """
    Retrieve persistent presence state for a zone/camera pair.
    """

    query = (
        db.query(
            ZonePresence
        )
        .filter(
            ZonePresence.zone_id
            == zone_id
        )
    )

    if camera_id is None:

        query = query.filter(
            ZonePresence.camera_id.is_(
                None
            )
        )

    else:

        query = query.filter(
            ZonePresence.camera_id
            == camera_id
        )

    return query.first()


def get_or_create_zone_presence(
    db: Session,
    zone_id: int,
    camera_id: int | None = None,
) -> ZonePresence:
    """
    Retrieve existing persistent zone presence state,
    or create it if it does not exist.
    """

    presence = get_zone_presence(
        db=db,
        zone_id=zone_id,
        camera_id=camera_id,
    )

    if presence is not None:
        return presence

    presence = ZonePresence(
        zone_id=zone_id,
        camera_id=camera_id,
        is_inside=False,
        last_seen_at=None,
    )

    db.add(
        presence
    )

    db.flush()

    return presence


def mark_zone_presence_inside(
    db: Session,
    presence: ZonePresence,
) -> bool:
    """
    Mark a zone as occupied.

    Returns True only when this is a new entry transition.

        False -> True = new entry
        True  -> True = person remains inside
    """

    was_inside = bool(
        presence.is_inside
    )

    now = utc_now()

    presence.is_inside = True
    presence.last_seen_at = now
    presence.updated_at = now

    db.add(
        presence
    )

    return not was_inside


def mark_zone_presence_outside(
    db: Session,
    presence: ZonePresence,
) -> bool:
    """
    Mark a zone as unoccupied.

    Returns True when an actual exit transition occurred.
    """

    was_inside = bool(
        presence.is_inside
    )

    now = utc_now()

    presence.is_inside = False
    presence.last_seen_at = now
    presence.updated_at = now

    db.add(
        presence
    )

    return was_inside


def update_zone_presence(
    db: Session,
    zone_id: int,
    camera_id: int | None,
    persons_in_zone: list[Any],
) -> bool:
    """
    Update persistent zone occupancy.

    Returns:

        True  -> new entry detected
        False -> no new entry

    State machine:

        OUTSIDE
            |
            | person detected
            v
        INSIDE
            |
            | person remains
            |
            | no person detected
            v
        OUTSIDE

    A new SafetyEvent is generated only for:

        OUTSIDE -> INSIDE

    This prevents duplicate events while a person
    remains inside the restricted zone.
    """

    presence = get_or_create_zone_presence(
        db=db,
        zone_id=zone_id,
        camera_id=camera_id,
    )

    if persons_in_zone:

        return mark_zone_presence_inside(
            db=db,
            presence=presence,
        )

    mark_zone_presence_outside(
        db=db,
        presence=presence,
    )

    return False


# ============================================================
# LEGACY / COMPATIBILITY COOLDOWN FUNCTION
# ============================================================

def has_recent_zone_event(
    db: Session,
    zone_id: int,
    camera_id: int | None = None,
    cooldown_seconds: int = 10,
) -> bool:
    """
    Backward-compatible helper used by older callers.

    Persistent ZonePresence is now the primary mechanism
    for preventing duplicate restricted-zone events.

    This function remains available for compatibility.
    """

    cutoff = (
        utc_now()
        -
        timedelta(
            seconds=cooldown_seconds
        )
    )

    query = (
        db.query(
            SafetyEvent
        )
        .filter(
            SafetyEvent.zone_id
            == zone_id,
            SafetyEvent.event_type
            == "restricted_zone_entry",
            SafetyEvent.occurred_at
            >= cutoff,
        )
    )

    if camera_id is None:

        query = query.filter(
            SafetyEvent.camera_id.is_(
                None
            )
        )

    else:

        query = query.filter(
            SafetyEvent.camera_id
            == camera_id
        )

    return (
        query.first()
        is not None
    )


# ============================================================
# RESTRICTED-ZONE EVENT
# ============================================================

def create_restricted_zone_event(
    db: Session,
    zone: Zone,
    person_detection: Any,
    camera_id: int | None = None,
) -> SafetyEvent:
    """
    Create one restricted-zone SafetyEvent.

    High-risk restricted-zone events are automatically
    converted into Incidents through the central
    SiteAegis incident pipeline.
    """

    confidence = get_detection_value(
        person_detection,
        "confidence",
    )

    if confidence is None:
        confidence = 0.0

    try:

        confidence = float(
            confidence
        )

    except (
        TypeError,
        ValueError,
    ):

        confidence = 0.0

    confidence = max(
        0.0,
        min(
            confidence,
            1.0,
        ),
    )

    risk_map = {
        "low": 30,
        "medium": 50,
        "high": 75,
        "critical": 95,
    }

    zone_risk = str(
        zone.risk_level
        or "high"
    ).strip().lower()

    risk_score = risk_map.get(
        zone_risk,
        75,
    )

    severity_map = {
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "critical",
    }

    severity = severity_map.get(
        zone_risk,
        "high",
    )

    now = utc_now()

    event = SafetyEvent(
        camera_id=camera_id,
        zone_id=zone.id,
        event_type="restricted_zone_entry",
        severity=severity,
        title="Restricted zone entry detected",
        description=(
            f"Person detected inside restricted zone "
            f"'{zone.name}'."
        ),
        confidence=confidence,
        detected_object="person",
        risk_score=risk_score,
        status="active",
        occurred_at=now,
        created_at=now,
    )

    db.add(
        event
    )

    db.flush()

    # --------------------------------------------------------
    # CENTRAL INCIDENT PIPELINE
    # --------------------------------------------------------
    #
    # This ensures high/critical restricted-zone events
    # create an Incident using the same mechanism as:
    #
    #   proximity
    #   fall detection
    #   unsafe movement
    #   other safety events
    #
    # Incident creation rules are centralized inside
    # incident_service.py.
    #

    create_incident_from_event(
        db=db,
        event=event,
    )

    return event