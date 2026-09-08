"""backfill scan site relationships

Revision ID: 894343289ace
Revises: f06d132289e4
Create Date: 2026-09-04 20:57:08.163240

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# ============================================================
# REVISION IDENTIFIERS
# ============================================================

revision: str = "894343289ace"

down_revision: Union[str, Sequence[str], None] = "f06d132289e4"

branch_labels: Union[str, Sequence[str], None] = None

depends_on: Union[str, Sequence[str], None] = None


# ============================================================
# UPGRADE
# ============================================================

def upgrade() -> None:
    """
    Associate existing scans with registered sites.

    Matching is performed using the exact URL.

    Only scans whose site_id is currently NULL
    will be updated.
    """

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE scans
            SET site_id = (
                SELECT sites.id
                FROM sites
                WHERE sites.url = scans.target_url
            )
            WHERE scans.site_id IS NULL
              AND EXISTS (
                  SELECT 1
                  FROM sites
                  WHERE sites.url = scans.target_url
              )
            """
        )
    )


# ============================================================
# DOWNGRADE
# ============================================================

def downgrade() -> None:
    """
    Remove the site relationships created by this
    backfill migration.

    Scan records themselves are preserved.
    """

    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE scans
            SET site_id = NULL
            WHERE site_id IS NOT NULL
              AND target_url IN (
                  SELECT url
                  FROM sites
              )
            """
        )
    )