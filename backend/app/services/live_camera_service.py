from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import cv2
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.camera import Camera
from app.models.safety_event import SafetyEvent
from app.services.video_analysis_service import analyze_frame
from app.services.vision_service import (
    VisionDetection,
    detect_objects_from_frame,
    detect_persons_from_frame,
)
from app.websocket.manager import manager


DEFAULT_FRAME_INTERVAL = 5
DEFAULT_LOOP_VIDEO = True

SUPPORTED_LOCAL_SOURCE_TYPES = {
    "video",
    "upload",
    "file",
}

SUPPORTED_STREAM_PREFIXES = (
    "rtsp://",
    "rtmp://",
    "http://",
    "https://",
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def resolve_camera_source(
    source_url: str,
) -> str:
    """
    Resolve a camera source.

    Relative local paths are resolved relative to the
    SiteAegis backend directory.

    URLs such as RTSP/RTMP/HTTP/HTTPS are returned unchanged.
    """

    if not source_url:
        raise ValueError("Camera source URL is empty.")

    source = source_url.strip()

    if source.lower().startswith(
        SUPPORTED_STREAM_PREFIXES
    ):
        return source

    backend_dir = Path(__file__).resolve().parents[2]

    source_path = Path(source)

    if not source_path.is_absolute():
        source_path = backend_dir / source_path

    source_path = source_path.resolve()

    if not source_path.exists():
        raise FileNotFoundError(
            f"Camera source not found: {source_path}"
        )

    if not source_path.is_file():
        raise ValueError(
            f"Camera source is not a file: {source_path}"
        )

    return str(source_path)


def serialize_event(
    event: SafetyEvent,
) -> dict[str, Any]:
    """
    Convert a SQLAlchemy SafetyEvent into a JSON-safe dict.
    """

    return {
        "id": event.id,
        "camera_id": event.camera_id,
        "zone_id": event.zone_id,
        "event_type": event.event_type,
        "severity": event.severity,
        "title": event.title,
        "description": event.description,
        "confidence": event.confidence,
        "detected_object": event.detected_object,
        "risk_score": event.risk_score,
        "status": event.status,
        "occurred_at": (
            event.occurred_at.isoformat()
            if event.occurred_at
            else None
        ),
    }


def collect_new_events(
    db: Session,
    event_ids_before: set[int],
) -> list[dict[str, Any]]:
    """
    Return SafetyEvents created since event_ids_before.
    """

    query = (
        db.query(SafetyEvent)
        .order_by(SafetyEvent.id.asc())
        .all()
    )

    new_events = [
        event
        for event in query
        if event.id not in event_ids_before
    ]

    return [
        serialize_event(event)
        for event in new_events
    ]


def broadcast_camera_event(
    camera_id: int,
    event: dict[str, Any],
) -> None:
    """
    Broadcast one safety event to connected dashboard clients.
    """

    manager.broadcast_sync(
        {
            "type": "camera_safety_event",
            "camera_id": camera_id,
            "event": event,
        }
    )


def broadcast_camera_status(
    camera_id: int,
    status: str,
    message: str | None = None,
) -> None:
    """
    Broadcast camera worker status.
    """

    payload: dict[str, Any] = {
        "type": "camera_analysis_status",
        "camera_id": camera_id,
        "status": status,
    }

    if message:
        payload["message"] = message

    manager.broadcast_sync(payload)


# ---------------------------------------------------------
# LIVE CAMERA WORKER
# ---------------------------------------------------------

class LiveCameraWorker:
    """
    Background worker for continuous camera/video analysis.

    Each worker owns its own SQLAlchemy session because the
    worker runs in a background thread.

    Important:
    Previous person detections are kept as the original
    VisionDetection objects so unsafe movement detection
    can compare consecutive frames correctly.
    """

    def __init__(
        self,
        camera_id: int,
        source: str,
        frame_interval: int = DEFAULT_FRAME_INTERVAL,
        loop_video: bool = DEFAULT_LOOP_VIDEO,
    ):
        self.camera_id = camera_id
        self.source = source

        self.frame_interval = max(
            1,
            int(frame_interval),
        )

        self.loop_video = bool(loop_video)

        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None

        self.status = "stopped"
        self.frames_read = 0
        self.frames_processed = 0
        self.events_created = 0
        self.last_error: str | None = None
        self.started_at: float | None = None
        self.last_frame_at: float | None = None

        self.previous_person_detections: (
            list[VisionDetection] | None
        ) = None

        self.lock = threading.Lock()

    # -----------------------------------------------------
    # LIFECYCLE
    # -----------------------------------------------------

    def start(self) -> None:
        with self.lock:
            if (
                self.thread is not None
                and self.thread.is_alive()
            ):
                return

            self.stop_event.clear()
            self.status = "starting"
            self.last_error = None
            self.started_at = time.time()

            self.thread = threading.Thread(
                target=self.run,
                name=(
                    f"siteaegis-camera-{self.camera_id}"
                ),
                daemon=True,
            )

            self.thread.start()

    def stop(
        self,
        timeout: float = 10.0,
    ) -> None:
        self.stop_event.set()

        thread = self.thread

        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout=timeout)

        with self.lock:
            if (
                self.thread is None
                or not self.thread.is_alive()
            ):
                self.status = "stopped"

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    def get_status(self) -> dict[str, Any]:
        with self.lock:
            thread_alive = (
                self.thread is not None
                and self.thread.is_alive()
            )

            return {
                "camera_id": self.camera_id,
                "status": self.status,
                "thread_alive": thread_alive,
                "source": self.source,
                "frame_interval": self.frame_interval,
                "loop_video": self.loop_video,
                "frames_read": self.frames_read,
                "frames_processed": (
                    self.frames_processed
                ),
                "events_created": self.events_created,
                "started_at": self.started_at,
                "last_frame_at": (
                    self.last_frame_at
                ),
                "last_error": self.last_error,
            }

    # -----------------------------------------------------
    # CAMERA DB STATUS
    # -----------------------------------------------------

    def update_camera_status(
        self,
        status: str,
    ) -> None:
        db = SessionLocal()

        try:
            camera = (
                db.query(Camera)
                .filter(
                    Camera.id == self.camera_id
                )
                .first()
            )

            if camera is None:
                return

            camera.status = status
            db.commit()

        except Exception as exc:
            db.rollback()

            with self.lock:
                self.last_error = str(exc)

        finally:
            db.close()

    # -----------------------------------------------------
    # FRAME ANALYSIS
    # -----------------------------------------------------

    def process_frame(
        self,
        db: Session,
        frame: Any,
    ) -> dict[str, Any]:
        """
        Analyze one frame.

        Person/object detections are performed here instead
        of relying on serialized output from analyze_frame.

        This is important because unsafe movement detection
        requires the original VisionDetection objects from
        consecutive frames.
        """

        current_person_detections = (
            detect_persons_from_frame(frame)
        )

        current_object_detections = (
            detect_objects_from_frame(frame)
        )

        result = analyze_frame(
            db=db,
            frame=frame,
            camera_id=self.camera_id,
            previous_person_detections=(
                self.previous_person_detections
            ),
            current_person_detections=(
                current_person_detections
            ),
            current_object_detections=(
                current_object_detections
            ),
        )

        # IMPORTANT:
        # Keep the raw VisionDetection objects for the next
        # frame so unsafe movement can compare them.
        self.previous_person_detections = (
            current_person_detections
        )

        return result

    # -----------------------------------------------------
    # MAIN LOOP
    # -----------------------------------------------------

    def run(self) -> None:
        db = SessionLocal()
        capture = None

        try:
            with self.lock:
                self.status = "starting"

            broadcast_camera_status(
                camera_id=self.camera_id,
                status="starting",
                message="Live camera worker starting.",
            )

            self.update_camera_status("online")

            capture = cv2.VideoCapture(
                self.source
            )

            if not capture.isOpened():
                raise RuntimeError(
                    "Could not open camera/video source."
                )

            with self.lock:
                self.status = "running"

            broadcast_camera_status(
                camera_id=self.camera_id,
                status="running",
                message="Live camera analysis is running.",
            )

            frame_index = 0

            while not self.stop_event.is_set():

                success, frame = capture.read()

                if not success:

                    # Local video files can be looped for
                    # continuous testing.
                    if (
                        self.loop_video
                        and not self.source.lower().startswith(
                            SUPPORTED_STREAM_PREFIXES
                        )
                    ):
                        capture.release()

                        capture = cv2.VideoCapture(
                            self.source
                        )

                        if capture.isOpened():
                            self.previous_person_detections = None
                            frame_index = 0
                            continue

                    break

                with self.lock:
                    self.frames_read += 1

                current_frame_index = frame_index
                frame_index += 1

                if (
                    current_frame_index
                    % self.frame_interval
                    != 0
                ):
                    continue

                if self.stop_event.is_set():
                    break

                event_ids_before = {
                    event.id
                    for event in (
                        db.query(SafetyEvent.id)
                        .all()
                    )
                }

                try:
                    result = self.process_frame(
                        db=db,
                        frame=frame,
                    )

                    db.commit()

                    new_events = (
                        collect_new_events(
                            db=db,
                            event_ids_before=(
                                event_ids_before
                            ),
                        )
                    )

                    with self.lock:
                        self.frames_processed += 1
                        self.events_created += len(
                            new_events
                        )
                        self.last_frame_at = (
                            time.time()
                        )

                    # Send newly created safety events
                    # immediately to connected dashboards.
                    for event in new_events:
                        broadcast_camera_event(
                            camera_id=self.camera_id,
                            event=event,
                        )

                    manager.broadcast_sync(
                        {
                            "type": "camera_analysis_frame",
                            "camera_id": (
                                self.camera_id
                            ),
                            "frame": result,
                        }
                    )

                except Exception as exc:
                    db.rollback()

                    with self.lock:
                        self.last_error = str(exc)

                    manager.broadcast_sync(
                        {
                            "type": "camera_analysis_error",
                            "camera_id": (
                                self.camera_id
                            ),
                            "error": str(exc),
                        }
                    )

                    # Continue processing subsequent frames
                    # instead of killing the whole worker.
                    time.sleep(0.2)

            with self.lock:
                if self.stop_event.is_set():
                    self.status = "stopped"
                else:
                    self.status = "completed"

            self.update_camera_status(
                "offline"
                if self.stop_event.is_set()
                else "online"
            )

            broadcast_camera_status(
                camera_id=self.camera_id,
                status=self.status,
                message=(
                    "Live camera worker stopped."
                    if self.stop_event.is_set()
                    else "Video source ended."
                ),
            )

        except FileNotFoundError as exc:
            with self.lock:
                self.status = "error"
                self.last_error = str(exc)

            self.update_camera_status("offline")

            broadcast_camera_status(
                camera_id=self.camera_id,
                status="error",
                message=str(exc),
            )

        except Exception as exc:
            with self.lock:
                self.status = "error"
                self.last_error = str(exc)

            self.update_camera_status("offline")

            broadcast_camera_status(
                camera_id=self.camera_id,
                status="error",
                message=str(exc),
            )

        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass

            db.close()

            with self.lock:
                if self.status not in {
                    "error",
                    "completed",
                }:
                    self.status = "stopped"


# ---------------------------------------------------------
# WORKER REGISTRY
# ---------------------------------------------------------

_workers: dict[
    int,
    LiveCameraWorker,
] = {}

_workers_lock = threading.Lock()


def start_live_camera(
    camera_id: int,
    source: str,
    frame_interval: int = DEFAULT_FRAME_INTERVAL,
    loop_video: bool = DEFAULT_LOOP_VIDEO,
) -> dict[str, Any]:
    """
    Start a live camera worker.

    If the camera already has a running worker, the existing
    worker status is returned.
    """

    with _workers_lock:

        existing = _workers.get(camera_id)

        if (
            existing is not None
            and existing.thread is not None
            and existing.thread.is_alive()
        ):
            return existing.get_status()

        worker = LiveCameraWorker(
            camera_id=camera_id,
            source=source,
            frame_interval=frame_interval,
            loop_video=loop_video,
        )

        _workers[camera_id] = worker

        worker.start()

        return worker.get_status()


def stop_live_camera(
    camera_id: int,
) -> dict[str, Any]:
    """
    Stop one camera worker.
    """

    with _workers_lock:
        worker = _workers.get(camera_id)

    if worker is None:
        return {
            "camera_id": camera_id,
            "status": "stopped",
            "message": "No live worker is running.",
        }

    worker.stop()

    result = worker.get_status()

    with _workers_lock:
        if (
            worker.thread is None
            or not worker.thread.is_alive()
        ):
            _workers.pop(
                camera_id,
                None,
            )

    return result


def get_live_camera_status(
    camera_id: int,
) -> dict[str, Any]:
    """
    Return current worker status.
    """

    with _workers_lock:
        worker = _workers.get(camera_id)

    if worker is None:
        return {
            "camera_id": camera_id,
            "status": "stopped",
            "thread_alive": False,
            "message": "No live worker is running.",
        }

    return worker.get_status()


def stop_all_live_cameras() -> None:
    """
    Stop every active live camera worker.

    Intended for application shutdown.
    """

    with _workers_lock:
        workers = list(
            _workers.values()
        )

    for worker in workers:
        try:
            worker.stop()
        except Exception:
            pass

    with _workers_lock:
        _workers.clear()