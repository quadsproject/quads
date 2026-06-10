"""add move_source_cloud to schedules

Revision ID: 324bab5d5ac5
Revises: a3f8b2d91c4e
Create Date: 2026-06-10 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "324bab5d5ac5"
down_revision = "a3f8b2d91c4e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("schedules", sa.Column("move_source_cloud", sa.String(), nullable=True))


def downgrade():
    op.drop_column("schedules", "move_source_cloud")
