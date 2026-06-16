"""add release_command to users

Revision ID: b03922beaffb
Revises: 324bab5d5ac5
Create Date: 2026-06-23 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b03922beaffb"
down_revision = "324bab5d5ac5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("release_command", sa.String(1024), nullable=True))


def downgrade():
    op.drop_column("users", "release_command")
