"""Default hosts to overcloud

Revision ID: 3bd119370bb0
Revises: 5c9e3f71ad84
Create Date: 2026-09-25 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "3bd119370bb0"
down_revision = "5c9e3f71ad84"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("hosts", "overcloud", server_default=sa.true())
    op.execute("UPDATE hosts SET overcloud = true WHERE overcloud IS NOT TRUE")


def downgrade():
    op.alter_column("hosts", "overcloud", server_default=sa.false())
