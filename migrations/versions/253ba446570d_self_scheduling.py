"""Self scheduling

Revision ID: 253ba446570d
Revises:
Create Date: 2024-12-11 21:21:31.166560

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "253ba446570d"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "assignments", sa.Column("is_self_schedule", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column("hosts", sa.Column("can_self_schedule", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    op.drop_column("assignments", "is_self_schedule")
    op.drop_column("hosts", "can_self_schedule")
