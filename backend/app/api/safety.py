from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.safety_event import (
    SafetyEventCreate,
    SafetyEventResponse,
    SafetyEventUpdate,
)
from app.services.safety_service import (
    create_safety_event,
    delete_safety_event,
    get_safety_event,
    get_safety_events,
    update_safety_event,
)


router = APIRouter(
    prefix="/safety",
    tags=["Safety Events"],
)


# ============================================================
# CREATE SAFETY EVENT
# ============================================================

@router.post(
    "/events",
    response_model=SafetyEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    event_data: SafetyEventCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new safety event.

    Validation and incident creation are handled
    by the safety service layer.
    """

    try:
        event = create_safety_event(
            db=db,
            event_data=event_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return event


# ============================================================
# GET ALL SAFETY EVENTS
# ============================================================

@router.get(
    "/events",
    response_model=list[SafetyEventResponse],
)
def get_events(
    db: Session = Depends(get_db),
):
    """
    Return all safety events, newest first.
    """

    return get_safety_events(
        db=db,
    )


# ============================================================
# GET SINGLE SAFETY EVENT
# ============================================================

@router.get(
    "/events/{event_id}",
    response_model=SafetyEventResponse,
)
def get_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Return a single safety event by ID.
    """

    event = get_safety_event(
        db=db,
        event_id=event_id,
    )

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    return event


# ============================================================
# UPDATE SAFETY EVENT
# ============================================================

@router.put(
    "/events/{event_id}",
    response_model=SafetyEventResponse,
)
def update_event(
    event_id: int,
    event_data: SafetyEventUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing safety event.

    Only explicitly supplied fields are modified.
    """

    try:
        event = update_safety_event(
            db=db,
            event_id=event_id,
            event_data=event_data,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    return event


# ============================================================
# DELETE SAFETY EVENT
# ============================================================

@router.delete(
    "/events/{event_id}",
)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a safety event by ID.
    """

    deleted = delete_safety_event(
        db=db,
        event_id=event_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Safety event not found",
        )

    return {
        "message": "Safety event deleted successfully",
        "event_id": event_id,
    }