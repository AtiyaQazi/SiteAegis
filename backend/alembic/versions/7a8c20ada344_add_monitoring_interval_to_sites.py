"""add monitoring interval to sites

Revision ID: 7a8c20ada344
Revises: 894343289ace
Create Date: 2026-09-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# REVISION IDENTIFIERS
# ============================================================

revision: str = "7a8c20ada344"

down_revision: Union[str, Sequence[str], None] = "894343289ace"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:
    """
    Add monitoring interval to existing sites.

    Existing sites receive a default interval of 60 minutes.
    """

    with op.batch_alter_table(
        "sites",
        schema=None,
    ) as batch_op:

        batch_op.add_column(
            sa.Column(
                "monitoring_interval_minutes",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("60"),
            )
        )


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:
    """Remove monitoring interval from sites."""

    with op.batch_alter_table(
        "sites",
        schema=None,
    ) as batch_op:

        batch_op.drop_column(
            "monitoring_interval_minutes"
        )