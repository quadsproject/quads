"""Added overcloud to host

Revision ID: cb3d1e473790
Revises: 0f6d1a14c8f5
Create Date: 2026-02-04 10:55:12.085550

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "cb3d1e473790"
down_revision = "0f6d1a14c8f5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("hosts", sa.Column("overcloud", sa.Boolean(), server_default=sa.false()))


def downgrade():
    op.drop_column("hosts", "overcloud")
