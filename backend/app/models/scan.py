from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Scan(Base):
    __tablename__ = "scans"

    # ========================================================
    # PRIMARY KEY
    # ========================================================

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    # ========================================================
    # SITE RELATIONSHIP
    # ========================================================

    site_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "sites.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # ========================================================
    # TARGET
    # ========================================================

    target_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    hostname: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # ========================================================
    # AVAILABILITY
    # ========================================================

    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    status_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    response_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    ip_address: Mapped[str | None] = mapped_column(
        String(45),
        nullable=True,
    )

    # ========================================================
    # SSL / TLS
    # ========================================================

    ssl_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    ssl_valid: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    ssl_issuer: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ssl_subject: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    ssl_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # SECURITY HEADERS
    # ========================================================

    security_headers_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    security_headers_total: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    security_headers: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    missing_headers: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    security_headers_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # RISK
    # ========================================================

    risk_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    risk_level: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    findings_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    severity_counts: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    findings: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # ========================================================
    # TIMESTAMP
    # ========================================================

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )