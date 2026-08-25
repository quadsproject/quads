"""Unit tests for the api_tokens.created_at server-default migration (5c9e3f71ad84).

The migration only alters schema (drops a server-side default on upgrade,
restores it on downgrade); the alembic ``op`` is stubbed so the calls are
asserted without a live database.
"""

import importlib

migration = importlib.import_module("migrations.versions.5c9e3f71ad84_drop_api_token_created_at_server_default")


class _RecordingOp:
    def __init__(self):
        self.alterations = []

    def alter_column(self, table, column, **kwargs):
        self.alterations.append((table, column, kwargs))


def test_upgrade_drops_created_at_default(monkeypatch):
    op = _RecordingOp()
    monkeypatch.setattr(migration, "op", op)
    migration.upgrade()
    assert op.alterations == [("api_tokens", "created_at", {"server_default": None})]


def test_downgrade_restores_created_at_default(monkeypatch):
    op = _RecordingOp()
    monkeypatch.setattr(migration, "op", op)
    migration.downgrade()
    assert len(op.alterations) == 1
    table, column, kwargs = op.alterations[0]
    assert (table, column) == ("api_tokens", "created_at")
    assert kwargs["server_default"] is not None
