"""Add OAuth fields to User model

Revision ID: a1b2c3d4e5f6
Revises: cb3d1e473790
Create Date: 2026-04-30 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "cb3d1e473790"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("google_id", sa.String(256), unique=True, nullable=True))
    op.add_column("users", sa.Column("profile_picture", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("last_login", sa.DateTime(), nullable=True))
    op.create_index("ix_users_google_id", "users", ["google_id"], unique=True)
    op.alter_column("users", "password", existing_type=sa.String(256), nullable=True)


def downgrade():
    op.alter_column("users", "password", existing_type=sa.String(256), nullable=False)
    op.drop_index("ix_users_google_id", table_name="users")
    op.drop_column("users", "last_login")
    op.drop_column("users", "profile_picture")
    op.drop_column("users", "google_id")
