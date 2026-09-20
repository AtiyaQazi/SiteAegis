from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ZonePresence(Base):
    __tablename__ = "zone_presence"

    __table_args__ = (
        UniqueConstraint(
            "zone_id",
            "camera_id",
            name="uq_zone_presence_zone_camera",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    zone_id: Mapped[int] = mapped_column(
        ForeignKey(
            "zones.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    camera_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "cameras.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    is_inside: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )