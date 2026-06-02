"""Move progress columns from move_progress table to schedules

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-04 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "schedules",
        sa.Column(
            "move_status",
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
            nullable=True,
        ),
    )
    op.add_column("schedules", sa.Column("move_message", sa.String(), nullable=True))
    op.add_column("schedules", sa.Column("move_error", sa.String(), nullable=True))

    op.execute(
        """
        UPDATE schedules SET
            move_status = mp.status,
            move_message = mp.message,
            move_error = mp.error_message
        FROM move_progress mp
        WHERE schedules.id = mp.schedule_id
          AND mp.status NOT IN ('completed', 'failed')
        """
    )

    op.create_index("ix_schedules_move_status", "schedules", ["move_status"])
    op.drop_index("ix_move_progress_host_status", table_name="move_progress")
    op.drop_table("move_progress")


def downgrade():
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
    op.drop_index("ix_schedules_move_status", table_name="schedules")
    op.drop_column("schedules", "move_error")
    op.drop_column("schedules", "move_message")
    op.drop_column("schedules", "move_status")
