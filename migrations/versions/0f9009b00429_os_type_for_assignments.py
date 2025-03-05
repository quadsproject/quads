"""Os type for assignments

Revision ID: 0f9009b00429
Revises: 071677379d4e
Create Date: 2025-01-17 07:08:52.220166

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0f9009b00429"
down_revision = "071677379d4e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("assignments", sa.Column("ostype", sa.String()))


def downgrade():
    op.drop_column("assignments", "ostype")
