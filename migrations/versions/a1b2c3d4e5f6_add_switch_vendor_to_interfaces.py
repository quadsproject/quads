"""Add switch_vendor to interfaces

Revision ID: a1b2c3d4e5f6
Revises: 965ac44a95f5
Create Date: 2026-05-28 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "965ac44a95f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interfaces", sa.Column("switch_vendor", sa.String(), nullable=True))


def downgrade():
    op.drop_column("interfaces", "switch_vendor")
