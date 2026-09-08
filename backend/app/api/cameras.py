from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.camera import Camera
from app.schemas.camera import CameraCreate, CameraResponse, CameraUpdate


router = APIRouter(
    prefix="/cameras",
    tags=["Cameras"],
)


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