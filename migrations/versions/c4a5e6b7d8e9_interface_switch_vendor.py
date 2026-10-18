"""Backfill switch_vendor for pre-existing interfaces

Revision ID: c4a5e6b7d8e9
Revises: e530c8f33513
Create Date: 2026-10-18 08:30:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c4a5e6b7d8e9"
down_revision = "e530c8f33513"
branch_labels = None
depends_on = None


def upgrade():
    # e530c8f33513 adds the column on the merged development branch; this
    # revision only teaches existing rows the historical vendor. Keeping the
    # backfill separate also preserves the revision already stamped by POC
    # installs built from the earlier generic-driver branch.
    op.execute("UPDATE interfaces SET switch_vendor = 'juniper' WHERE switch_vendor IS NULL")


def downgrade():
    # The column is owned by e530c8f33513; a data backfill is not reversed
    # because clearing it would erase explicitly configured switch vendors.
    pass
