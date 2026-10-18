"""Add switch_vendor to interfaces

Revision ID: c4a5e6b7d8e9
Revises: 3bd119370bb0
Create Date: 2026-10-18 08:30:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "c4a5e6b7d8e9"
down_revision = "3bd119370bb0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("interfaces", sa.Column("switch_vendor", sa.String(), nullable=True))


def downgrade():
    op.drop_column("interfaces", "switch_vendor")
