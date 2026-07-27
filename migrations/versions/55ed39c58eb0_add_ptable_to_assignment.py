"""Add ptable to assignment

Revision ID: 55ed39c58eb0
Revises: cf4d6cca178b
Create Date: 2026-07-24 13:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "55ed39c58eb0"
down_revision = "cf4d6cca178b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assignments", sa.Column("ptable", sa.String()))


def downgrade():
    op.drop_column("assignments", "ptable")
