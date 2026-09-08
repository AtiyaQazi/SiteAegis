from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # REFERENCES
    # ========================================================

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
    # EVENT INFORMATION
    # ========================================================

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    severity: Mapped[str] = mapped_column(
        String(20),
        default="low",
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # AI / VISION INFORMATION
    # ========================================================

    confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    detected_object: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # ========================================================
    # RISK
    # ========================================================

    risk_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        index=True,
    )

    # ========================================================
    # EVENT STATUS
    # ========================================================

    status: Mapped[str] = mapped_column(
        String(30),
        default="active",
        nullable=False,
        index=True,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )