"""add move_stage_timestamps to schedules

Revision ID: 44ead5705c86
Revises: 324bab5d5ac5
Create Date: 2026-06-16 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "44ead5705c86"
down_revision = "324bab5d5ac5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("schedules", sa.Column("move_stage_timestamps", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("schedules", "move_stage_timestamps")
