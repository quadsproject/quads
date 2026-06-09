"""add ssh_key field to users

Revision ID: a3f8b2d91c4e
Revises: 1c622a2059f2
Create Date: 2026-06-09

"""

from alembic import op
import sqlalchemy as sa

revision = "a3f8b2d91c4e"
down_revision = "1c622a2059f2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("ssh_key", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("users", "ssh_key")
