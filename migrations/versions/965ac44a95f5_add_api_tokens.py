"""Add API tokens table

Revision ID: 965ac44a95f5
Revises: cf4d6cca178b
Create Date: 2026-05-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "965ac44a95f5"
down_revision = "cf4d6cca178b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("token_prefix", sa.String(12), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("last_used", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)
    op.create_index("ix_api_tokens_user_id", "api_tokens", ["user_id"])
    op.create_unique_constraint("uq_api_tokens_user_id_name", "api_tokens", ["user_id", "name"])


def downgrade():
    op.drop_constraint("uq_api_tokens_user_id_name", "api_tokens")
    op.drop_index("ix_api_tokens_user_id", table_name="api_tokens")
    op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
    op.drop_table("api_tokens")
