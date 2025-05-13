"""added boot_order to assignment

Revision ID: 157838206445
Revises: e9b96f886b77
Create Date: 2025-05-13 19:12:38.671992

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "157838206445"
down_revision = "e9b96f886b77"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assignments", sa.Column("boot_order", sa.VARCHAR(), autoincrement=False, nullable=True))


def downgrade():
    op.drop_column("assignments", "boot_order")
