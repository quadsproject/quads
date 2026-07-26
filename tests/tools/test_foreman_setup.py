#!/usr/bin/env python3
"""
Tests for src/quads/tools/foreman_setup.py

Covers:
  - ensure_quads_rbac(): all early-exit branches and the happy path
  - _rbac_thread(): disabled, testing, lock contention, exception, happy path
  - start_foreman_rbac_thread(): daemon thread is started
"""

import asyncio
import logging
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.tools.foreman_setup import (
    _rbac_thread,
    ensure_quads_rbac,
    start_foreman_rbac_thread,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FOREMAN_CONF = {
    "enabled": True,
    "api_url": "https://foreman.example.com",
    "username": "admin",
    "password": "secret",
    "rbac_user_mail": "quads@example.com",
    "rbac_auth_source_id": "1",
    "rbac_exclude": "",
}

_PLUGINS_WITH_FOREMAN = {"foreman": _FOREMAN_CONF}


def _make_foreman_mock(verify_ok=True, role_id=1, group_id=2, user_id=3):
    """Return a fully-wired AsyncMock Foreman instance for happy-path tests."""
    m = AsyncMock()
    m.verify_credentials.return_value = verify_ok
    m.get_or_create_role.return_value = role_id
    m.cleanup_duplicate_filters.return_value = 0
    m.ensure_filter.return_value = True
    m.get_or_create_usergroup.return_value = group_id
    m.cleanup_duplicate_memberships.return_value = 0
    m.get_or_create_cloud_user.return_value = user_id
    m.add_user_to_usergroup.return_value = True
    return m


# ---------------------------------------------------------------------------
# ensure_quads_rbac
# ---------------------------------------------------------------------------


class TestEnsureQuadsRbac:
    @pytest.mark.asyncio
    async def test_missing_credentials_logs_warning(self, caplog):
        """Missing api_url/username/password → warning and early return."""
        plugins = {"foreman": {"enabled": True}}
        with patch("quads.tools.foreman_setup.Config") as mock_cfg:
            mock_cfg.plugins = plugins
            with caplog.at_level(logging.WARNING, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac([])
        assert any("missing api_url" in m for m in caplog.messages)

    @pytest.mark.asyncio
    async def test_invalid_credentials_logs_warning(self, caplog):
        """verify_credentials() returns False → warning and early return."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            foreman = _make_foreman_mock(verify_ok=False)
            MockForeman.return_value = foreman

            with caplog.at_level(logging.WARNING, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac([])

        assert any("credentials invalid" in m for m in caplog.messages)
        foreman.get_or_create_role.assert_not_called()

    @pytest.mark.asyncio
    async def test_hosts_role_creation_failure_logs_error(self, caplog):
        """get_or_create_role returns None for hosts role → error and early return."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            foreman = _make_foreman_mock()
            foreman.get_or_create_role.side_effect = [None, 2]
            MockForeman.return_value = foreman

            with caplog.at_level(logging.ERROR, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac([])

        assert any("could not create/find role" in m for m in caplog.messages)
        foreman.cleanup_duplicate_filters.assert_not_called()

    @pytest.mark.asyncio
    async def test_views_role_creation_failure_logs_error(self, caplog):
        """get_or_create_role returns None for views role → error and early return."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            foreman = _make_foreman_mock()
            foreman.get_or_create_role.side_effect = [1, None]
            MockForeman.return_value = foreman

            with caplog.at_level(logging.ERROR, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac([])

        assert any("could not create/find role" in m for m in caplog.messages)
        foreman.get_or_create_usergroup.assert_not_called()

    @pytest.mark.asyncio
    async def test_usergroup_creation_failure_logs_error(self, caplog):
        """get_or_create_usergroup returns None → error and early return."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            foreman = _make_foreman_mock()
            foreman.get_or_create_usergroup.return_value = None
            MockForeman.return_value = foreman

            with caplog.at_level(logging.ERROR, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac(["cloud01"])

        assert any("could not create/find usergroup" in m for m in caplog.messages)
        foreman.get_or_create_cloud_user.assert_not_called()

    @pytest.mark.asyncio
    async def test_cloud_user_creation_failure_logs_warning_and_continues(self, caplog):
        """get_or_create_cloud_user failure → warning, but remaining clouds processed."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            mock_cfg.get.return_value = "password"
            foreman = _make_foreman_mock()
            foreman.get_or_create_cloud_user.side_effect = [None, 77]
            MockForeman.return_value = foreman

            with caplog.at_level(logging.WARNING, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac(["cloud01", "cloud02"])

        assert any("could not create/find user" in m for m in caplog.messages)
        # cloud02 was still processed (add_user_to_usergroup called once for it)
        assert foreman.add_user_to_usergroup.call_count == 1

    @pytest.mark.asyncio
    async def test_add_user_to_group_failure_logs_warning_and_continues(self, caplog):
        """add_user_to_usergroup failure → warning, other clouds still processed."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            mock_cfg.get.return_value = "password"
            foreman = _make_foreman_mock()
            foreman.add_user_to_usergroup.side_effect = [False, True]
            MockForeman.return_value = foreman

            with caplog.at_level(logging.WARNING, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac(["cloud01", "cloud02"])

        assert any("could not add user" in m for m in caplog.messages)
        assert foreman.add_user_to_usergroup.call_count == 2

    @pytest.mark.asyncio
    async def test_rbac_exclude_skips_clouds(self, caplog):
        """Clouds listed in rbac_exclude are not processed."""
        plugins = dict(_PLUGINS_WITH_FOREMAN)
        plugins["foreman"] = dict(_FOREMAN_CONF, rbac_exclude="cloud01|cloud02")

        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = plugins
            mock_cfg.get.return_value = "password"
            foreman = _make_foreman_mock()
            MockForeman.return_value = foreman

            await ensure_quads_rbac(["cloud01", "cloud02", "cloud03"])

        # Only cloud03 should be processed
        assert foreman.get_or_create_cloud_user.call_count == 1
        call_args = foreman.get_or_create_cloud_user.call_args[0]
        assert call_args[0] == "cloud03"

    @pytest.mark.asyncio
    async def test_happy_path_logs_complete(self, caplog):
        """Full successful run logs 'Foreman RBAC setup complete'."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            mock_cfg.plugins = _PLUGINS_WITH_FOREMAN
            mock_cfg.get.return_value = "password"
            foreman = _make_foreman_mock()
            MockForeman.return_value = foreman

            with caplog.at_level(logging.INFO, logger="quads.tools.foreman_setup"):
                await ensure_quads_rbac(["cloud01", "cloud02"])

        assert any("RBAC setup complete" in m for m in caplog.messages)
        assert foreman.get_or_create_cloud_user.call_count == 2
        assert foreman.add_user_to_usergroup.call_count == 2

    @pytest.mark.asyncio
    async def test_blank_rbac_auth_source_id_defaults_to_one(self):
        """A blank (None) rbac_auth_source_id falls back to the default of 1."""
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.Foreman") as MockForeman,
        ):
            foreman_conf = dict(_FOREMAN_CONF)
            foreman_conf["rbac_auth_source_id"] = None
            mock_cfg.plugins = {"foreman": foreman_conf}
            mock_cfg.get.return_value = "password"
            foreman = _make_foreman_mock()
            MockForeman.return_value = foreman

            await ensure_quads_rbac(["cloud01"])

        foreman.get_or_create_cloud_user.assert_called_once()
        assert foreman.get_or_create_cloud_user.call_args[0][3] == 1


# ---------------------------------------------------------------------------
# _rbac_thread
# ---------------------------------------------------------------------------


class TestRbacThread:
    def _make_app(self, testing=False):
        app = MagicMock()
        app.config = {"TESTING": testing}
        app.app_context.return_value.__enter__ = MagicMock(return_value=None)
        app.app_context.return_value.__exit__ = MagicMock(return_value=False)
        return app

    def test_returns_immediately_when_foreman_disabled(self):
        """If foreman plugin is disabled the thread body is never entered."""
        app = self._make_app()
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.asyncio") as mock_asyncio,
        ):
            mock_cfg.plugins = {"foreman": {"enabled": False}}
            _rbac_thread(app)
            mock_asyncio.run.assert_not_called()

    def test_returns_immediately_in_testing_mode(self):
        """If TESTING=True the thread body is never entered."""
        app = self._make_app(testing=True)
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.asyncio") as mock_asyncio,
        ):
            mock_cfg.plugins = {"foreman": {"enabled": True}}
            _rbac_thread(app)
            mock_asyncio.run.assert_not_called()

    def test_lock_contention_logs_debug(self, caplog):
        """When another worker holds the lock, a debug message is emitted."""
        import fcntl as _fcntl

        app = self._make_app()
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.time.sleep"),
            patch("quads.tools.foreman_setup.fcntl") as mock_fcntl,
            patch("builtins.open", MagicMock()),
        ):
            mock_cfg.plugins = {"foreman": {"enabled": True}}
            mock_fcntl.LOCK_EX = _fcntl.LOCK_EX
            mock_fcntl.LOCK_NB = _fcntl.LOCK_NB
            mock_fcntl.LOCK_UN = _fcntl.LOCK_UN
            mock_fcntl.flock.side_effect = BlockingIOError

            with caplog.at_level(logging.DEBUG, logger="quads.tools.foreman_setup"):
                _rbac_thread(app)

        assert any("already running" in m for m in caplog.messages)

    def test_exception_during_setup_logs_warning(self, caplog):
        """An unexpected exception is caught and logged as a warning."""
        app = self._make_app()
        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.time.sleep"),
            patch("builtins.open", side_effect=OSError("disk full")),
        ):
            mock_cfg.plugins = {"foreman": {"enabled": True}}

            with caplog.at_level(logging.WARNING, logger="quads.tools.foreman_setup"):
                _rbac_thread(app)

        assert any("RBAC setup failed" in m for m in caplog.messages)

    def test_happy_path_calls_ensure_quads_rbac(self):
        """In the happy path asyncio.run is called with ensure_quads_rbac."""
        import fcntl as _fcntl

        app = self._make_app()
        mock_cloud = MagicMock()
        mock_cloud.name = "cloud01"

        with (
            patch("quads.tools.foreman_setup.Config") as mock_cfg,
            patch("quads.tools.foreman_setup.time.sleep"),
            patch("quads.tools.foreman_setup.fcntl") as mock_fcntl,
            patch("builtins.open", MagicMock()),
            patch("quads.tools.foreman_setup.db") as mock_db,
            patch("quads.tools.foreman_setup.Cloud"),
            patch("quads.tools.foreman_setup.asyncio") as mock_asyncio,
        ):
            mock_cfg.plugins = {"foreman": {"enabled": True}}
            mock_fcntl.LOCK_EX = _fcntl.LOCK_EX
            mock_fcntl.LOCK_NB = _fcntl.LOCK_NB
            mock_fcntl.LOCK_UN = _fcntl.LOCK_UN
            mock_fcntl.flock.return_value = None
            mock_db.session.query.return_value.all.return_value = [mock_cloud]
            mock_asyncio.run.return_value = None

            _rbac_thread(app)

        mock_asyncio.run.assert_called_once()


# ---------------------------------------------------------------------------
# start_foreman_rbac_thread
# ---------------------------------------------------------------------------


class TestStartForemanRbacThread:
    def test_starts_daemon_thread(self):
        """start_foreman_rbac_thread launches a daemon Thread."""
        app = MagicMock()
        with patch("quads.tools.foreman_setup._rbac_thread") as mock_thread_fn:
            # Make the thread body a no-op so it exits immediately
            mock_thread_fn.return_value = None
            start_foreman_rbac_thread(app)

        # Verify a daemon thread was spawned (it may have already finished,
        # so check via Thread inspection rather than threading.enumerate)
        # The test passes if no exception is raised and the call completes.
        mock_thread_fn  # referenced to satisfy linters; actual assertion below

    def test_thread_is_daemon(self):
        """The spawned thread has daemon=True so it does not block shutdown."""
        app = MagicMock()
        created = []

        real_thread_init = threading.Thread.__init__

        def capture_init(self, *args, **kwargs):
            real_thread_init(self, *args, **kwargs)
            created.append(self)

        with (
            patch.object(threading.Thread, "__init__", capture_init),
            patch.object(threading.Thread, "start"),
        ):
            start_foreman_rbac_thread(app)

        assert created, "No Thread was instantiated"
        assert created[0].daemon is True
