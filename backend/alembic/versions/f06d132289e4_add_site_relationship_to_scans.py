"""add site relationship to scans

Revision ID: f06d132289e4
Revises:
Create Date: 2026-09-04 20:41:41.675998

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# REVISION IDENTIFIERS
# ============================================================

revision: str = "f06d132289e4"

down_revision: Union[str, Sequence[str], None] = None

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:
    """
    Add nullable site_id relationship to scans table.
    """

    with op.batch_alter_table("scans", schema=None) as batch_op:

        batch_op.add_column(
            sa.Column(
                "site_id",
                sa.Integer(),
                nullable=True,
            )
        )

        batch_op.create_index(
            "ix_scans_site_id",
            ["site_id"],
            unique=False,
        )

        batch_op.create_foreign_key(
            "fk_scans_site_id_sites",
            "sites",
            ["site_id"],
            ["id"],
            ondelete="SET NULL",
        )


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:
    """
    Remove site_id relationship from scans table.
    """

    with op.batch_alter_table("scans", schema=None) as batch_op:

        batch_op.drop_constraint(
            "fk_scans_site_id_sites",
            type_="foreignkey",
        )

        batch_op.drop_index(
            "ix_scans_site_id"
        )

        batch_op.drop_column(
            "site_id"
        )