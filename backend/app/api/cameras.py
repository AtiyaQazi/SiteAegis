from pathlib import Path
import shutil
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate
from app.services.live_camera_service import (
    get_live_camera_status,
    resolve_camera_source,
    start_live_camera,
    stop_live_camera,
)
from app.services.video_analysis_service import analyze_video


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


# ---------------------------------------------------------
# CAMERA CRUD
# ---------------------------------------------------------


@router.post(
    "",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_camera(
    camera_data: CameraCreate,
    db: Session = Depends(get_db),
):
    camera = Camera(
        name=camera_data.name,
        location=camera_data.location,
        description=camera_data.description,
        source_type=camera_data.source_type,
        source_url=camera_data.source_url,
        is_active=camera_data.is_active,
        status="offline",
    )

    db.add(camera)
    db.commit()
    db.refresh(camera)

    return camera


@router.get(
    "",
    response_model=list[CameraResponse],
)
def get_cameras(
    db: Session = Depends(get_db),
):
    return (
        db.query(Camera)
        .order_by(Camera.id.desc())
        .all()
    )


@router.get(
    "/{camera_id}",
    response_model=CameraResponse,
)
def get_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    return camera


@router.put(
    "/{camera_id}",
    response_model=CameraResponse,
)
def update_camera(
    camera_id: int,
    camera_data: CameraUpdate,
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    update_data = camera_data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(camera, field, value)

    db.commit()
    db.refresh(camera)

    return camera


@router.delete(
    "/{camera_id}",
)
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
):
    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    db.delete(camera)
    db.commit()

    return {
        "message": "Camera deleted successfully",
        "camera_id": camera_id,
    }


# ---------------------------------------------------------
# VIDEO ANALYSIS
# ---------------------------------------------------------


@router.post(
    "/{camera_id}/analyze",
)
def analyze_camera_video(
    camera_id: int,
    file: UploadFile | None = File(default=None),
    frame_interval: int = 5,
    max_frames: int | None = None,
    max_seconds: float | None = None,
    db: Session = Depends(get_db),
):
    """
    Analyze a video for a camera.

    If a video file is uploaded using the `file` form field,
    that uploaded video is analyzed directly.

    If no file is uploaded, the endpoint falls back to the
    camera's configured source_url.

    Supported safety analysis includes:

    - Restricted-zone entry
    - Worker-machine proximity
    - Crowding
    - Fall detection
    - Unsafe movement
    """

    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera is inactive",
        )

    if camera.source_type not in {
        "video",
        "upload",
        "file",
    } and file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Camera source type is not supported "
                "for local video analysis"
            ),
        )

    # -----------------------------------------------------
    # VALIDATE PARAMETERS
    # -----------------------------------------------------

    if frame_interval < 1:
        frame_interval = 1

    if max_frames is not None and max_frames < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_frames must be greater than 0",
        )

    if max_seconds is not None and max_seconds <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_seconds must be greater than 0",
        )

    # -----------------------------------------------------
    # RESOLVE VIDEO PATH
    # -----------------------------------------------------

    backend_dir = Path(__file__).resolve().parents[2]

    uploaded_file_path: Path | None = None

    if file is not None:
        """
        Uploaded file takes priority over camera.source_url.
        This is important for testing different videos without
        changing the configured camera source.
        """

        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file has no filename",
            )

        original_name = Path(file.filename).name
        extension = Path(original_name).suffix.lower()

        allowed_extensions = {
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".webm",
            ".mpeg",
            ".mpg",
        }

        if extension not in allowed_extensions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Unsupported video format. "
                    "Allowed formats: "
                    "mp4, avi, mov, mkv, webm, mpeg, mpg"
                ),
            )

        upload_dir = backend_dir / "uploads" / "videos"
        upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        safe_filename = (
            f"camera_{camera.id}_"
            f"{uuid.uuid4().hex}"
            f"{extension}"
        )

        uploaded_file_path = (
            upload_dir / safe_filename
        )

        try:
            with uploaded_file_path.open(
                "wb"
            ) as buffer:
                shutil.copyfileobj(
                    file.file,
                    buffer,
                )

        except Exception as exc:
            if uploaded_file_path.exists():
                uploaded_file_path.unlink(
                    missing_ok=True
                )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    f"Could not save uploaded video: {exc}"
                ),
            )

        source_path = uploaded_file_path.resolve()

    else:
        if not camera.source_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Camera has no configured video source",
            )

        source_path = Path(camera.source_url)

        if not source_path.is_absolute():
            source_path = backend_dir / source_path

        source_path = source_path.resolve()

    # -----------------------------------------------------
    # VALIDATE VIDEO FILE
    # -----------------------------------------------------

    if not source_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video source not found: {source_path}",
        )

    if not source_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Video source is not a file: {source_path}",
        )

    # -----------------------------------------------------
    # MARK CAMERA ONLINE
    # -----------------------------------------------------

    camera.status = "online"

    db.commit()
    db.refresh(camera)

    # -----------------------------------------------------
    # RUN VIDEO ANALYZER
    # -----------------------------------------------------

    try:
        result = analyze_video(
            db=db,
            video_path=source_path,
            camera_id=camera.id,
            frame_interval=frame_interval,
            max_frames=max_frames,
            max_seconds=max_seconds,
        )

    except FileNotFoundError as exc:
        camera.status = "offline"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except ValueError as exc:
        camera.status = "offline"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    except RuntimeError as exc:
        camera.status = "offline"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )

    except Exception as exc:
        camera.status = "offline"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Video analysis failed: {exc}",
        )

    finally:
        if file is not None:
            try:
                awaitable_close = file.file.close()

                if awaitable_close is not None:
                    pass

            except Exception:
                pass

    # -----------------------------------------------------
    # KEEP CAMERA ONLINE AFTER SUCCESS
    # -----------------------------------------------------

    camera.status = "online"

    db.commit()
    db.refresh(camera)

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "source_type": camera.source_type,
            "source_url": camera.source_url,
            "status": camera.status,
            "is_active": camera.is_active,
        },
        "analysis_source": {
            "type": "upload" if file is not None else "camera_source",
            "original_filename": (
                file.filename
                if file is not None
                else None
            ),
            "path": str(source_path),
        },
        "analysis": result,
    }


# ---------------------------------------------------------
# LIVE CAMERA ANALYSIS
# ---------------------------------------------------------


@router.post(
    "/{camera_id}/live/start",
)
def start_camera_live_analysis(
    camera_id: int,
    frame_interval: int = 5,
    loop_video: bool = True,
    db: Session = Depends(get_db),
):
    """
    Start continuous background AI analysis for a camera.

    Supports local video files and stream sources such as:

    - local video/file/upload
    - RTSP
    - RTMP
    - HTTP
    - HTTPS
    """

    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    if not camera.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera is inactive",
        )

    if not camera.source_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Camera has no configured source",
        )

    if frame_interval < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="frame_interval must be greater than 0",
        )

    if camera.source_type not in {
        "video",
        "upload",
        "file",
        "rtsp",
        "rtmp",
        "stream",
        "http",
        "https",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Camera source type is not supported "
                "for live analysis"
            ),
        )

    try:
        source = resolve_camera_source(
            camera.source_url
        )

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    try:
        worker_status = start_live_camera(
            camera_id=camera.id,
            source=source,
            frame_interval=frame_interval,
            loop_video=loop_video,
        )

    except Exception as exc:
        camera.status = "offline"
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not start live analysis: {exc}",
        )

    camera.status = "online"

    db.commit()
    db.refresh(camera)

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "source_type": camera.source_type,
            "source_url": camera.source_url,
            "status": camera.status,
            "is_active": camera.is_active,
        },
        "live_analysis": worker_status,
    }


@router.post(
    "/{camera_id}/live/stop",
)
def stop_camera_live_analysis(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """
    Stop continuous background AI analysis for a camera.
    """

    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    try:
        worker_status = stop_live_camera(
            camera_id=camera.id
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not stop live analysis: {exc}",
        )

    camera.status = "offline"

    db.commit()
    db.refresh(camera)

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "source_type": camera.source_type,
            "source_url": camera.source_url,
            "status": camera.status,
            "is_active": camera.is_active,
        },
        "live_analysis": worker_status,
    }


@router.get(
    "/{camera_id}/live/status",
)
def get_camera_live_status(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """
    Return the current background live-analysis status.
    """

    camera = (
        db.query(Camera)
        .filter(Camera.id == camera_id)
        .first()
    )

    if camera is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Camera not found",
        )

    worker_status = get_live_camera_status(
        camera_id=camera.id
    )

    return {
        "camera": {
            "id": camera.id,
            "name": camera.name,
            "source_type": camera.source_type,
            "source_url": camera.source_url,
            "status": camera.status,
            "is_active": camera.is_active,
        },
        "live_analysis": worker_status,
    }