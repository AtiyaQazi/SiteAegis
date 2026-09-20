from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
from sqlalchemy.orm import Session

from app.models.zone import Zone

from app.services.crowding_service import (
    process_crowding,
)

from app.services.fall_detection_service import (
    process_fall_detection,
)

from app.services.proximity_service import (
    process_worker_machine_proximity,
)

from app.services.unsafe_movement_service import (
    process_unsafe_movement,
)

from app.services.vision_service import (
    detect_objects_from_frame,
    detect_persons_from_frame,
)

from app.services.zone_service import (
    create_restricted_zone_event,
    detect_persons_in_zone,
    update_zone_presence,
)


# ============================================================
# DEFAULT SETTINGS
# ============================================================

DEFAULT_FRAME_INTERVAL = 5

DEFAULT_PERSON_CONFIDENCE = 0.25

DEFAULT_OBJECT_CONFIDENCE = 0.25


# ============================================================
# DETECTION SERIALIZATION
# ============================================================

def detection_to_dict(
    detection: Any,
) -> dict:
    """
    Convert a VisionDetection object into a normal
    dictionary suitable for API/WebSocket responses.
    """

    if detection is None:
        return {}

    if hasattr(
        detection,
        "to_dict",
    ):
        return detection.to_dict()

    if isinstance(
        detection,
        dict,
    ):
        return detection

    return {
        "label": getattr(
            detection,
            "label",
            None,
        ),
        "confidence": getattr(
            detection,
            "confidence",
            None,
        ),
        "detected_object": getattr(
            detection,
            "detected_object",
            None,
        ),
        "metadata": getattr(
            detection,
            "metadata",
            {},
        ),
    }


def detections_to_dicts(
    detections: list[Any],
) -> list[dict]:
    """
    Convert a list of VisionDetection objects to dictionaries.
    """

    return [
        detection_to_dict(
            detection
        )
        for detection in detections
    ]


# ============================================================
# EVENT SERIALIZATION
# ============================================================

def serialize_event(
    event: Any,
) -> dict | None:
    """
    Convert a SafetyEvent SQLAlchemy object into a
    JSON-safe dictionary.
    """

    if event is None:
        return None

    if isinstance(
        event,
        dict,
    ):
        return event

    created_at = getattr(
        event,
        "created_at",
        None,
    )

    if created_at is not None:
        try:
            created_at = created_at.isoformat()
        except Exception:
            created_at = str(
                created_at
            )

    return {
        "id": getattr(
            event,
            "id",
            None,
        ),
        "event_type": getattr(
            event,
            "event_type",
            getattr(
                event,
                "type",
                None,
            ),
        ),
        "severity": getattr(
            event,
            "severity",
            None,
        ),
        "risk_score": getattr(
            event,
            "risk_score",
            None,
        ),
        "camera_id": getattr(
            event,
            "camera_id",
            None,
        ),
        "zone_id": getattr(
            event,
            "zone_id",
            None,
        ),
        "status": getattr(
            event,
            "status",
            None,
        ),
        "confidence": getattr(
            event,
            "confidence",
            None,
        ),
        "description": getattr(
            event,
            "description",
            None,
        ),
        "created_at": created_at,
    }


# ============================================================
# SAFETY RESULT SERIALIZATION
# ============================================================

def serialize_safety_result(
    result: Any,
) -> Any:
    """
    Convert service results containing SQLAlchemy SafetyEvent
    objects into JSON-safe dictionaries.
    """

    if result is None:
        return None

    if isinstance(
        result,
        dict,
    ):

        serialized = {}

        for key, value in result.items():

            if key == "safety_event":

                serialized[key] = serialize_event(
                    value
                )

            elif key == "safety_events":

                if isinstance(
                    value,
                    list,
                ):

                    serialized[key] = [
                        serialize_event(
                            event
                        )
                        for event in value
                    ]

                else:

                    serialized[key] = value

            else:

                serialized[key] = value

        return serialized

    return result


# ============================================================
# RESTRICTED ZONE PROCESSING
# ============================================================

def process_restricted_zones(
    db: Session,
    person_detections: list[Any],
    image_width: int,
    image_height: int,
    camera_id: int | None = None,
) -> dict:
    """
    Analyze detected persons against every configured
    restricted zone.

    Persistent zone-presence state machine:

        OUTSIDE
            |
            | person detected
            v
        INSIDE
            |
            | person remains
            v
        INSIDE
            |
            | no person detected
            v
        OUTSIDE

    A SafetyEvent is created only on:

        OUTSIDE -> INSIDE

    Therefore:

        first entry       = 1 event
        staying inside   = 0 events
        exit              = 0 events
        re-entry          = 1 new event

    Multiple people inside the same zone during the
    same detection cycle still produce only one
    restricted-zone entry event.
    """

    zones = (
        db.query(
            Zone
        )
        .order_by(
            Zone.id.asc()
        )
        .all()
    )

    zone_detections = []

    events_created = []

    for zone in zones:

        if not zone.polygon:
            continue

        # ----------------------------------------------------
        # Detect people inside this zone.
        # ----------------------------------------------------

        try:

            inside_persons = (
                detect_persons_in_zone(
                    zone=zone,
                    detections=person_detections,
                    image_width=image_width,
                    image_height=image_height,
                )
            )

        except Exception as exc:

            print(
                "[VIDEO][ZONE] "
                f"Detection failed for zone "
                f"{zone.id}: {exc}"
            )

            continue

        # ----------------------------------------------------
        # Update persistent zone presence.
        #
        # IMPORTANT:
        #
        # This is performed even when inside_persons
        # is empty so that:
        #
        #     INSIDE -> OUTSIDE
        #
        # is detected and the state can reset.
        # ----------------------------------------------------

        try:

            is_new_entry = (
                update_zone_presence(
                    db=db,
                    zone_id=zone.id,
                    camera_id=camera_id,
                    persons_in_zone=inside_persons,
                )
            )

        except Exception as exc:

            print(
                "[VIDEO][ZONE] "
                f"Presence update failed for zone "
                f"{zone.id}: {exc}"
            )

            continue

        # ----------------------------------------------------
        # Record every person detected inside the zone.
        # ----------------------------------------------------

        for person_detection in inside_persons:

            zone_detections.append(
                {
                    "zone_id": zone.id,
                    "zone_name": zone.name,
                    "risk_level": zone.risk_level,
                    "detection": detection_to_dict(
                        person_detection
                    ),
                    "event_created": False,
                    "safety_event": None,
                    "new_entry": is_new_entry,
                }
            )

        # ----------------------------------------------------
        # CREATE ONE EVENT FOR NEW ENTRY ONLY
        # ----------------------------------------------------
        #
        # IMPORTANT:
        #
        # We intentionally do NOT loop here.
        #
        # If two or ten people enter the same restricted
        # zone during the same detection cycle, SiteAegis
        # creates ONE zone-entry event.
        # ----------------------------------------------------

        if (
            is_new_entry
            and inside_persons
        ):

            person_detection = (
                inside_persons[0]
            )

            try:

                event = (
                    create_restricted_zone_event(
                        db=db,
                        zone=zone,
                        person_detection=(
                            person_detection
                        ),
                        camera_id=camera_id,
                    )
                )

                if event is not None:

                    events_created.append(
                        event
                    )

                    # Mark the first detected person
                    # as the person that generated the
                    # zone-entry event.

                    for record in reversed(
                        zone_detections
                    ):

                        if (
                            record["zone_id"]
                            == zone.id
                            and
                            record["safety_event"]
                            is None
                        ):

                            record[
                                "event_created"
                            ] = True

                            record[
                                "safety_event"
                            ] = serialize_event(
                                event
                            )

                            break

            except Exception as exc:

                print(
                    "[VIDEO][ZONE] "
                    f"Event creation failed: {exc}"
                )

    return {
        "zones_checked": len(
            zones
        ),
        "entries_detected": len(
            zone_detections
        ),
        "events_created": len(
            events_created
        ),
        "detections": zone_detections,
        "safety_events": [
            serialize_event(
                event
            )
            for event in events_created
        ],
    }


# ============================================================
# SINGLE FRAME ANALYSIS
# ============================================================

def analyze_frame(
    db: Session,
    frame: Any,
    camera_id: int | None = None,
    previous_person_detections: list[Any] | None = None,
    current_person_detections: list[Any] | None = None,
    current_object_detections: list[Any] | None = None,
) -> dict:
    """
    Analyze one OpenCV frame.

    Pipeline:

        OpenCV frame
             |
             +--------------------+
             |                    |
             v                    v
        Object/PPE             Persons
        detection              detection
             |                    |
             |          +---------+---------+
             |          |         |         |
             |          v         v         v
             |       crowding   fall    movement
             |
             +---------> proximity
                              |
                              v
                       restricted zones

    Existing safety services remain responsible for
    creating SafetyEvents and Incidents.
    """

    if frame is None:

        raise ValueError(
            "Frame cannot be None."
        )

    if not hasattr(
        frame,
        "shape",
    ):

        raise ValueError(
            "Invalid OpenCV frame."
        )

    if len(
        frame.shape
    ) < 2:

        raise ValueError(
            "Invalid OpenCV frame dimensions."
        )

    image_height, image_width = (
        frame.shape[:2]
    )

    # --------------------------------------------------------
    # OBJECT / PPE DETECTION
    # --------------------------------------------------------

    if current_object_detections is None:

        try:

            object_detections = (
                detect_objects_from_frame(
                    frame=frame,
                    minimum_confidence=(
                        DEFAULT_OBJECT_CONFIDENCE
                    ),
                )
            )

        except Exception as exc:

            print(
                "[VIDEO][VISION] "
                f"Object detection failed: {exc}"
            )

            object_detections = []

    else:

        object_detections = (
            current_object_detections
        )

    # --------------------------------------------------------
    # PERSON DETECTION
    # --------------------------------------------------------

    if current_person_detections is None:

        try:

            person_detections = (
                detect_persons_from_frame(
                    frame=frame,
                    minimum_confidence=(
                        DEFAULT_PERSON_CONFIDENCE
                    ),
                )
            )

        except Exception as exc:

            print(
                "[VIDEO][VISION] "
                f"Person detection failed: {exc}"
            )

            person_detections = []

    else:

        person_detections = (
            current_person_detections
        )

    # --------------------------------------------------------
    # CROWDING
    # --------------------------------------------------------

    crowding_result = None

    try:

        crowding_result = (
            process_crowding(
                db=db,
                detections=person_detections,
                camera_id=camera_id,
            )
        )

        crowding_result = (
            serialize_safety_result(
                crowding_result
            )
        )

    except Exception as exc:

        print(
            "[VIDEO][CROWDING] "
            f"Processing failed: {exc}"
        )

        try:
            db.rollback()
        except Exception:
            pass

    # --------------------------------------------------------
    # FALL DETECTION
    # --------------------------------------------------------

    fall_result = None

    try:

        fall_result = (
            process_fall_detection(
                db=db,
                detections=person_detections,
                camera_id=camera_id,
            )
        )

        fall_result = (
            serialize_safety_result(
                fall_result
            )
        )

    except Exception as exc:

        print(
            "[VIDEO][FALL] "
            f"Processing failed: {exc}"
        )

        try:
            db.rollback()
        except Exception:
            pass

    # --------------------------------------------------------
    # WORKER-MACHINE PROXIMITY
    # --------------------------------------------------------

    proximity_result = None

    combined_detections = (
        list(object_detections)
        + list(person_detections)
    )

    try:

        proximity_result = (
            process_worker_machine_proximity(
                db=db,
                detections=combined_detections,
                camera_id=camera_id,
            )
        )

        proximity_result = (
            serialize_safety_result(
                proximity_result
            )
        )

    except Exception as exc:

        print(
            "[VIDEO][PROXIMITY] "
            f"Processing failed: {exc}"
        )

        try:
            db.rollback()
        except Exception:
            pass

    # --------------------------------------------------------
    # UNSAFE MOVEMENT
    # --------------------------------------------------------

    movement_result = None

    if previous_person_detections is not None:

        try:

            movement_result = (
                process_unsafe_movement(
                    db=db,
                    previous_detections=(
                        previous_person_detections
                    ),
                    current_detections=(
                        person_detections
                    ),
                    camera_id=camera_id,
                )
            )

            movement_result = (
                serialize_safety_result(
                    movement_result
                )
            )

        except Exception as exc:

            print(
                "[VIDEO][MOVEMENT] "
                f"Processing failed: {exc}"
            )

            try:
                db.rollback()
            except Exception:
                pass

    # --------------------------------------------------------
    # RESTRICTED ZONES
    # --------------------------------------------------------

    zone_result = None

    try:

        zone_result = (
            process_restricted_zones(
                db=db,
                person_detections=(
                    person_detections
                ),
                image_width=image_width,
                image_height=image_height,
                camera_id=camera_id,
            )
        )

        zone_result = (
            serialize_safety_result(
                zone_result
            )
        )

    except Exception as exc:

        print(
            "[VIDEO][ZONE] "
            f"Processing failed: {exc}"
        )

        try:
            db.rollback()
        except Exception:
            pass

    # --------------------------------------------------------
    # FINAL COMMIT
    # --------------------------------------------------------

    try:

        db.commit()

    except Exception as exc:

        print(
            "[VIDEO][DATABASE] "
            f"Commit failed: {exc}"
        )

        db.rollback()

    # --------------------------------------------------------
    # RETURN RESULT
    # --------------------------------------------------------

    return {
        "frame": {
            "width": image_width,
            "height": image_height,
        },

        "objects": (
            detections_to_dicts(
                object_detections
            )
        ),

        "persons": (
            detections_to_dicts(
                person_detections
            )
        ),

        "crowding": crowding_result,

        "fall": fall_result,

        "proximity": proximity_result,

        "unsafe_movement": movement_result,

        "restricted_zones": zone_result,
    }


# ============================================================
# VIDEO FILE ANALYSIS
# ============================================================

def analyze_video(
    db: Session,
    video_path: str | Path,
    camera_id: int | None = None,
    frame_interval: int = DEFAULT_FRAME_INTERVAL,
    max_frames: int | None = None,
    max_seconds: float | None = None,
) -> dict:
    """
    Analyze a local video file.

    Parameters
    ----------
    db:
        SQLAlchemy database session.

    video_path:
        Local video path.

    camera_id:
        Optional camera ID associated with the analysis.

    frame_interval:
        Process every Nth frame.

        Example:
            1 = every frame
            5 = every fifth frame
            10 = every tenth frame

    max_frames:
        Optional maximum number of processed frames.

    max_seconds:
        Optional video-time limit.

    The function intentionally keeps video processing
    synchronous for the first validated implementation.
    """

    video_path = (
        Path(video_path)
        .resolve()
    )

    if not video_path.exists():

        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    if not video_path.is_file():

        raise ValueError(
            f"Video path is not a file: {video_path}"
        )

    if frame_interval < 1:
        frame_interval = 1

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = float(
        capture.get(
            cv2.CAP_PROP_FPS
        )
        or 0.0
    )

    total_frames = int(
        capture.get(
            cv2.CAP_PROP_FRAME_COUNT
        )
        or 0
    )

    width = int(
        capture.get(
            cv2.CAP_PROP_FRAME_WIDTH
        )
        or 0
    )

    height = int(
        capture.get(
            cv2.CAP_PROP_FRAME_HEIGHT
        )
        or 0
    )

    read_frames = 0

    processed_frames = 0

    previous_person_detections = None

    frame_results = []

    started_at = time.time()

    try:

        while True:

            success, frame = (
                capture.read()
            )

            if not success:
                break

            current_frame_number = (
                read_frames
            )

            read_frames += 1

            # ------------------------------------------------
            # MAX PROCESSED FRAMES
            # ------------------------------------------------

            if (
                max_frames is not None
                and processed_frames
                >= max_frames
            ):
                break

            # ------------------------------------------------
            # MAX VIDEO TIME
            # ------------------------------------------------

            if (
                max_seconds is not None
                and fps > 0
            ):

                current_seconds = (
                    current_frame_number
                    / fps
                )

                if (
                    current_seconds
                    >= max_seconds
                ):
                    break

            # ------------------------------------------------
            # FRAME INTERVAL
            # ------------------------------------------------

            if (
                current_frame_number
                % frame_interval
                != 0
            ):

                continue

            # ------------------------------------------------
            # DETECT PERSONS ONCE
            # ------------------------------------------------

            try:

                current_person_detections = (
                    detect_persons_from_frame(
                        frame=frame,
                        minimum_confidence=(
                            DEFAULT_PERSON_CONFIDENCE
                        ),
                    )
                )

            except Exception as exc:

                print(
                    "[VIDEO][VISION] "
                    f"Person detection failed "
                    f"on frame "
                    f"{current_frame_number}: "
                    f"{exc}"
                )

                current_person_detections = []

            # ------------------------------------------------
            # DETECT OBJECTS ONCE
            # ------------------------------------------------

            try:

                current_object_detections = (
                    detect_objects_from_frame(
                        frame=frame,
                        minimum_confidence=(
                            DEFAULT_OBJECT_CONFIDENCE
                        ),
                    )
                )

            except Exception as exc:

                print(
                    "[VIDEO][VISION] "
                    f"Object detection failed "
                    f"on frame "
                    f"{current_frame_number}: "
                    f"{exc}"
                )

                current_object_detections = []

            # ------------------------------------------------
            # ANALYZE FRAME
            # ------------------------------------------------

            result = analyze_frame(
                db=db,
                frame=frame,
                camera_id=camera_id,
                previous_person_detections=(
                    previous_person_detections
                ),
                current_person_detections=(
                    current_person_detections
                ),
                current_object_detections=(
                    current_object_detections
                ),
            )

            processed_frames += 1

            # ------------------------------------------------
            # KEEP ORIGINAL VISION DETECTIONS
            # ------------------------------------------------

            previous_person_detections = (
                current_person_detections
            )

            # ------------------------------------------------
            # FRAME RESULT
            # ------------------------------------------------

            timestamp_seconds = None

            if fps > 0:

                timestamp_seconds = (
                    current_frame_number
                    / fps
                )

            frame_results.append(
                {
                    "frame_number": (
                        current_frame_number
                    ),
                    "timestamp_seconds": (
                        timestamp_seconds
                    ),
                    "analysis": result,
                }
            )

    finally:

        capture.release()

    elapsed_seconds = (
        time.time()
        - started_at
    )

    # --------------------------------------------------------
    # FINAL SUMMARY
    # --------------------------------------------------------

    return {
        "video": {
            "path": str(
                video_path
            ),
            "fps": fps,
            "total_frames": total_frames,
            "width": width,
            "height": height,
        },

        "processing": {
            "frames_read": read_frames,
            "frames_processed": (
                processed_frames
            ),
            "frame_interval": (
                frame_interval
            ),
            "elapsed_seconds": round(
                elapsed_seconds,
                3,
            ),
        },

        "results": frame_results,
    }


# ============================================================
# VIDEO METADATA
# ============================================================

def get_video_metadata(
    video_path: str | Path,
) -> dict:
    """
    Read video metadata without running YOLO.
    """

    video_path = (
        Path(video_path)
        .resolve()
    )

    if not video_path.exists():

        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    if not video_path.is_file():

        raise ValueError(
            f"Video path is not a file: "
            f"{video_path}"
        )

    capture = cv2.VideoCapture(
        str(video_path)
    )

    if not capture.isOpened():

        raise RuntimeError(
            f"Could not open video: "
            f"{video_path}"
        )

    try:

        fps = float(
            capture.get(
                cv2.CAP_PROP_FPS
            )
            or 0.0
        )

        frame_count = int(
            capture.get(
                cv2.CAP_PROP_FRAME_COUNT
            )
            or 0
        )

        width = int(
            capture.get(
                cv2.CAP_PROP_FRAME_WIDTH
            )
            or 0
        )

        height = int(
            capture.get(
                cv2.CAP_PROP_FRAME_HEIGHT
            )
            or 0
        )

        duration_seconds = 0.0

        if fps > 0:

            duration_seconds = (
                frame_count
                / fps
            )

        return {
            "path": str(
                video_path
            ),
            "fps": fps,
            "frame_count": frame_count,
            "width": width,
            "height": height,
            "duration_seconds": round(
                duration_seconds,
                3,
            ),
        }

    finally:

        capture.release()