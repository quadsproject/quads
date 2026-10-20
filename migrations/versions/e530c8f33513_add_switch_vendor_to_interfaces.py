"""Add switch_vendor to interfaces

Revision ID: e530c8f33513
Revises: 3bd119370bb0
Create Date: 2026-10-20 09:51:03.463752

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "e530c8f33513"
down_revision = "3bd119370bb0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interfaces", sa.Column("switch_vendor", sa.String(), nullable=True))


def downgrade():
    op.drop_column("interfaces", "switch_vendor")
