from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.alert import Alert


router = APIRouter(
    prefix="/alerts",
    tags=["Alerts"],
)


def build_alert_response(alert: Alert) -> dict:
    return {
        "alert_id": str(alert.id),
        "site_id": str(alert.site_id),
        "event_id": (
            str(alert.event_id)
            if alert.event_id is not None
            else None
        ),
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "title": alert.title,
        "message": alert.message,
        "is_read": alert.is_read,
        "created_at": alert.created_at,
    }


@router.get("")
def get_alerts(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    """
    Return alerts newest first.
    """

    query = db.query(Alert)

    if unread_only:
        query = query.filter(
            Alert.is_read.is_(False)
        )

    alerts = (
        query
        .order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )

    return [
        build_alert_response(alert)
        for alert in alerts
    ]


@router.get("/unread")
def get_unread_alerts(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
    ),
    db: Session = Depends(get_db),
):
    """
    Return unread alerts only.
    """

    alerts = (
        db.query(Alert)
        .filter(
            Alert.is_read.is_(False)
        )
        .order_by(
            Alert.created_at.desc()
        )
        .limit(limit)
        .all()
    )

    return [
        build_alert_response(alert)
        for alert in alerts
    ]


@router.get("/count")
def get_alert_count(
    db: Session = Depends(get_db),
):
    """
    Return total and unread alert counts.
    """

    total = db.query(Alert).count()

    unread = (
        db.query(Alert)
        .filter(
            Alert.is_read.is_(False)
        )
        .count()
    )

    return {
        "total": total,
        "unread": unread,
    }


@router.patch("/{alert_id}/read")
def mark_alert_as_read(
    alert_id: int,
    db: Session = Depends(get_db),
):
    """
    Mark one alert as read.
    """

    alert = (
        db.query(Alert)
        .filter(Alert.id == alert_id)
        .first()
    )

    if not alert:
        raise HTTPException(
            status_code=404,
            detail="Alert not found.",
        )

    alert.is_read = True

    db.commit()
    db.refresh(alert)

    return {
        "status": "success",
        "message": "Alert marked as read.",
        "alert": build_alert_response(alert),
    }


@router.patch("/read-all")
def mark_all_alerts_as_read(
    db: Session = Depends(get_db),
):
    """
    Mark all unread alerts as read.
    """

    updated_count = (
        db.query(Alert)
        .filter(
            Alert.is_read.is_(False)
        )
        .update(
            {
                Alert.is_read: True
            },
            synchronize_session=False,
        )
    )

    db.commit()

    return {
        "status": "success",
        "updated_count": updated_count,
        "message": (
            "All unread alerts marked as read."
        ),
    }