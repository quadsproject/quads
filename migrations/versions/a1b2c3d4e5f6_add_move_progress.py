"""Add move_progress table

Revision ID: a1b2c3d4e5f6
Revises: 965ac44a95f5
Create Date: 2026-06-02 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "965ac44a95f5"
branch_labels = None
depends_on = None


def upgrade():
    move_status_enum = sa.Enum(
        "pending",
        "switch_config",
        "ipmi_config",
        "hardware_prep",
        "power_on",
        "provisioning",
        "cleanup",
        "reboot",
        "post_install",
        "foreman_rbac",
        "validation",
        "released",
        "completed",
        "failed",
        name="move_status_enum",
    )
    move_status_enum.create(op.get_bind())

    op.create_table(
        "move_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("hosts.id"), nullable=False),
        sa.Column("schedule_id", sa.Integer(), sa.ForeignKey("schedules.id"), nullable=True),
        sa.Column("source_cloud", sa.String(), nullable=False),
        sa.Column("target_cloud", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "switch_config",
                "ipmi_config",
                "hardware_prep",
                "power_on",
                "provisioning",
                "cleanup",
                "reboot",
                "post_install",
                "foreman_rbac",
                "validation",
                "released",
                "completed",
                "failed",
                name="move_status_enum",
                create_type=False,
            ),
            default="pending",
        ),
        sa.Column("message", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_move_progress_host_status", "move_progress", ["host_id", "status"])


def downgrade():
    op.drop_index("ix_move_progress_host_status", table_name="move_progress")
    op.drop_table("move_progress")

    move_status_enum = sa.Enum(name="move_status_enum")
    move_status_enum.drop(op.get_bind())
