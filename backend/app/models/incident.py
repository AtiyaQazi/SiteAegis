from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # SOURCE EVENT
    # ========================================================

    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("safety_events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    zone_id: Mapped[int | None] = mapped_column(
        ForeignKey("zones.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ========================================================
    # INCIDENT INFORMATION
    # ========================================================

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    incident_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    # ========================================================
    # SEVERITY / RISK
    # ========================================================

    severity: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
        index=True,
    )

    risk_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )

    # ========================================================
    # INCIDENT STATUS
    # ========================================================

    status: Mapped[str] = mapped_column(
        String(30),
        default="open",
        nullable=False,
        index=True,
    )

    # ========================================================
    # RESOLUTION
    # ========================================================

    resolution_notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )