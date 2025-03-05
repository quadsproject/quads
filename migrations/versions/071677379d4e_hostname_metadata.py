"""Hostname metadata

Revision ID: 071677379d4e
Revises: 253ba446570d
Create Date: 2025-01-17 06:17:12.541605

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "071677379d4e"
down_revision = "253ba446570d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hosts", sa.Column("rack", sa.String()))
    op.add_column("hosts", sa.Column("uloc", sa.String()))
    op.add_column("hosts", sa.Column("blade", sa.String()))


def downgrade():
    op.drop_column("hosts", "rack")
    op.drop_column("hosts", "uloc")
    op.drop_column("hosts", "blade")
