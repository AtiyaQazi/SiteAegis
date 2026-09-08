"""add monitoring events

Revision ID: c3e91b7a4f21
Revises: 7a8c20ada344
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3e91b7a4f21"

down_revision: Union[
    str,
    Sequence[str],
    None
] = "7a8c20ada344"

branch_labels: Union[
    str,
    Sequence[str],
    None
] = None

depends_on: Union[
    str,
    Sequence[str],
    None
] = None


def upgrade() -> None:

    op.create_table(
        "monitoring_events",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "site_id",
            sa.Integer(),
            sa.ForeignKey(
                "sites.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "scan_id",
            sa.Integer(),
            sa.ForeignKey(
                "scans.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "event_type",
            sa.String(length=50),
            nullable=False,
        ),

        sa.Column(
            "severity",
            sa.String(length=20),
            nullable=False,
        ),

        sa.Column(
            "title",
            sa.String(length=255),
            nullable=False,
        ),

        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "previous_value",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "current_value",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_monitoring_events_id",
        "monitoring_events",
        ["id"],
    )

    op.create_index(
        "ix_monitoring_events_site_id",
        "monitoring_events",
        ["site_id"],
    )

    op.create_index(
        "ix_monitoring_events_scan_id",
        "monitoring_events",
        ["scan_id"],
    )

    op.create_index(
        "ix_monitoring_events_event_type",
        "monitoring_events",
        ["event_type"],
    )

    op.create_index(
        "ix_monitoring_events_created_at",
        "monitoring_events",
        ["created_at"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_monitoring_events_created_at",
        table_name="monitoring_events",
    )

    op.drop_index(
        "ix_monitoring_events_event_type",
        table_name="monitoring_events",
    )

    op.drop_index(
        "ix_monitoring_events_scan_id",
        table_name="monitoring_events",
    )

    op.drop_index(
        "ix_monitoring_events_site_id",
        table_name="monitoring_events",
    )

    op.drop_index(
        "ix_monitoring_events_id",
        table_name="monitoring_events",
    )

    op.drop_table("monitoring_events")