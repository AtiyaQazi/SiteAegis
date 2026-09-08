from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Site(Base):
    __tablename__ = "sites"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # SITE INFORMATION
    # ========================================================

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
        unique=True,
    )

    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # ========================================================
    # MONITORING
    # ========================================================

    monitoring_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    monitoring_interval_minutes: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )

    # ========================================================
    # LAST SCAN SNAPSHOT
    # ========================================================

    last_scan_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    last_status: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    last_risk_score: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    last_risk_level: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    # ========================================================
    # TIMESTAMPS
    # ========================================================

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