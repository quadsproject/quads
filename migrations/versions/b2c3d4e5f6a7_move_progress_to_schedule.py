"""move progress on schedules

Revision ID: 1c622a2059f2
Revises: 965ac44a95f5
Create Date: 2026-06-05 15:02:56.085682

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1c622a2059f2"
down_revision = "965ac44a95f5"
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
            move_status = CASE
                WHEN start < NOW() THEN 'completed'
                ELSE 'pending'
            END
        """
    )

    op.create_index("ix_schedules_move_status", "schedules", ["move_status"])


def downgrade():
    op.drop_index("ix_schedules_move_status", table_name="schedules")
    op.drop_column("schedules", "move_error")
    op.drop_column("schedules", "move_message")
    op.drop_column("schedules", "move_status")
