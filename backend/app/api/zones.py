from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.zone import Zone
from app.schemas.zone import ZoneCreate, ZoneResponse, ZoneUpdate


router = APIRouter(
    prefix="/zones",
    tags=["Zones"],
)


@router.post(
    "",
    response_model=ZoneResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_zone(
    zone_data: ZoneCreate,
    db: Session = Depends(get_db),
):
    zone = Zone(
        name=zone_data.name,
        description=zone_data.description,
        location=zone_data.location,
        risk_level=zone_data.risk_level,
    )

    db.add(zone)
    db.commit()
    db.refresh(zone)

    return zone


@router.get(
    "",
    response_model=list[ZoneResponse],
)
def get_zones(
    db: Session = Depends(get_db),
):
    return (
        db.query(Zone)
        .order_by(Zone.id.desc())
        .all()
    )


@router.get(
    "/{zone_id}",
    response_model=ZoneResponse,
)
def get_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    return zone


@router.put(
    "/{zone_id}",
    response_model=ZoneResponse,
)
def update_zone(
    zone_id: int,
    zone_data: ZoneUpdate,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    update_data = zone_data.model_dump(
        exclude_unset=True,
    )

    for field, value in update_data.items():
        setattr(zone, field, value)

    db.commit()
    db.refresh(zone)

    return zone


@router.delete(
    "/{zone_id}",
)
def delete_zone(
    zone_id: int,
    db: Session = Depends(get_db),
):
    zone = (
        db.query(Zone)
        .filter(Zone.id == zone_id)
        .first()
    )

    if zone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Zone not found",
        )

    db.delete(zone)
    db.commit()

    return {
        "message": "Zone deleted successfully",
        "zone_id": zone_id,
    }