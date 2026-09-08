"""add alerts

Revision ID: 9cd339e204ad
Revises: c3e91b7a4f21
Create Date: 2026-09-04

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9cd339e204ad"
down_revision: Union[str, Sequence[str], None] = "c3e91b7a4f21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",

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
            "event_id",
            sa.Integer(),
            sa.ForeignKey(
                "monitoring_events.id",
                ondelete="SET NULL",
            ),
            nullable=True,
        ),

        sa.Column(
            "alert_type",
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
            "message",
            sa.Text(),
            nullable=False,
        ),

        sa.Column(
            "is_read",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
        ),
    )

    op.create_index(
        "ix_alerts_id",
        "alerts",
        ["id"],
    )

    op.create_index(
        "ix_alerts_site_id",
        "alerts",
        ["site_id"],
    )

    op.create_index(
        "ix_alerts_event_id",
        "alerts",
        ["event_id"],
    )

    op.create_index(
        "ix_alerts_alert_type",
        "alerts",
        ["alert_type"],
    )

    op.create_index(
        "ix_alerts_severity",
        "alerts",
        ["severity"],
    )

    op.create_index(
        "ix_alerts_is_read",
        "alerts",
        ["is_read"],
    )

    op.create_index(
        "ix_alerts_created_at",
        "alerts",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alerts_created_at",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_is_read",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_severity",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_alert_type",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_event_id",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_site_id",
        table_name="alerts",
    )

    op.drop_index(
        "ix_alerts_id",
        table_name="alerts",
    )

    op.drop_table("alerts")