"""Normalize database-generated timestamps to application local time

Revision ID: 5c9e3f71ad84
Revises: b03922beaffb
Create Date: 2026-09-02 00:00:00.000000

Timestamp columns that used the ``func.now()`` default stored the database
session wall clock.  The timestamp serialization (issue #709) now assumes the
application local wall clock everywhere, so historical rows must be shifted by
``(application offset - database offset)`` to remain accurate when the two
timezones differ.  This migration is a no-op for deployments where both offsets
match (the standard all-UTC deployment).

Run ``flask --app quads.server.app db upgrade`` at deploy time, before the new
application writes rows with application-side defaults, so that only historical
rows are shifted.
"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op

revision = "5c9e3f71ad84"
down_revision = "b03922beaffb"
branch_labels = None
depends_on = None

#: (table, column) pairs whose values had a single origin until this change:
#: either the database session (``func.now()`` defaults) or aware-UTC writes
#: stored into a naive column.  ``clouds.last_redefined`` is deliberately not
#: included: it is written by ``datetime.now()`` on every assignment change, so
#: its rows have mixed provenance that a single shift cannot repair.
TIMESTAMP_COLUMNS = (
    ("assignments", "created_at"),
    ("hosts", "created_at"),
    ("schedules", "created_at"),
    ("api_tokens", "created_at"),
    ("api_tokens", "last_used"),
    ("users", "last_login"),
)


def _offset_delta():
    conn = op.get_bind()
    db_offset = conn.execute(sa.text("SELECT EXTRACT(TIMEZONE FROM now())::int")).scalar()
    app_offset = int(datetime.now().astimezone().utcoffset().total_seconds())
    return app_offset - db_offset


def _shift(delta, sign):
    for table, column in TIMESTAMP_COLUMNS:
        op.execute(
            sa.text(
                f"UPDATE {table} SET {column} = {column} {sign} make_interval(secs => :delta) "
                f"WHERE {column} IS NOT NULL"
            ).bindparams(delta=delta)
        )


def upgrade():
    delta = _offset_delta()
    if delta:
        _shift(delta, "+")


def downgrade():
    delta = _offset_delta()
    if delta:
        _shift(delta, "-")
