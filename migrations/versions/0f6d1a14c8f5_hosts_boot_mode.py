"""Hosts boot mode

Revision ID: 0f6d1a14c8f5
Revises: 157838206445
Create Date: 2026-01-20 15:20:55.811223

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0f6d1a14c8f5"
down_revision = "157838206445"
branch_labels = None
depends_on = None


def upgrade():
    bootmode_enum = sa.Enum("Bios", "Uefi", name="bootmode_enum")
    bootmode_enum.create(op.get_bind())

    op.add_column("hosts", sa.Column("bootmode", sa.Enum("Bios", "Uefi", name="bootmode_enum"), nullable=True))


def downgrade():
    op.drop_column("hosts", "bootmode")

    bootmode_enum = sa.Enum(name="bootmode_enum")
    bootmode_enum.drop(op.get_bind())
