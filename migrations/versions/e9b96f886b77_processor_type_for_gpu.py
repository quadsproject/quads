"""Processor type for GPU

Revision ID: e9b96f886b77
Revises: 0f9009b00429
Create Date: 2025-02-27 13:00:11.826762

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e9b96f886b77"
down_revision = "0f9009b00429"
branch_labels = None
depends_on = None


def upgrade():
    processor_type_enum = sa.Enum("CPU", "GPU", name="processor_type_enum")
    processor_type_enum.create(op.get_bind())

    op.add_column(
        "processors", sa.Column("processor_type", sa.Enum("CPU", "GPU", name="processor_type_enum"), nullable=True)
    )


def downgrade():
    op.drop_column("processors", "processor_type")

    processor_type_enum = sa.Enum(name="processor_type_enum")
    processor_type_enum.drop(op.get_bind())
