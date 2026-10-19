"""Tests for dayzero plugin system"""

import asyncio
import logging
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from quads.plugins.base import BasePlugin
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.dispatchers.dayzero import DayzeroDispatcher
from quads.plugins.manager import PluginManager
from tests.plugins.conftest import (
    MockDayzeroPlugin,
    MockCloudDataPlugin,
    FailingDayzeroPlugin,
)


class TestDayzeroInterface:
    """Test DayzeroPlugin interface"""

    def test_dayzero_plugin_is_base_plugin(self):
        assert issubclass(DayzeroPlugin, BasePlugin)

    def test_dayzero_plugin_requires_execute(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):

            class IncompleteDayzeroPlugin(DayzeroPlugin):
                name = "incomplete"

            IncompleteDayzeroPlugin({})

    def test_dayzero_plugin_complete_implementation(self):

        class CompleteDayzeroPlugin(DayzeroPlugin):
            name = "complete"

            async def execute(self, cloud):
                return True

        plugin = CompleteDayzeroPlugin({})
        assert plugin is not None
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True

    def test_run_mode_can_be_set(self):
        class CustomDayzeroPlugin(DayzeroPlugin):
            name = "custom"
            run_mode = "per_cloud"

            async def execute(self, cloud):
                return True

        plugin = CustomDayzeroPlugin({})
        assert plugin.run_mode == "per_cloud"


class TestDayzeroDispatcher:
    """Test DayzeroDispatcher"""

    @pytest.fixture
    def setup_manager_with_dayzero(self):
        manager = PluginManager(config={})
        manager.available_plugins = {"mock_dayzero": MockDayzeroPlugin}
        manager.load_plugin("mock_dayzero", {"enabled": True})
        return manager

    @pytest.fixture
    def setup_manager_with_two_dayzero(self):
        manager = PluginManager(config={})
        manager.available_plugins = {
            "mock_dayzero": MockDayzeroPlugin,
            "mock_clouddata": MockCloudDataPlugin,
        }
        manager.load_plugin("mock_dayzero", {"enabled": True})
        manager.load_plugin("mock_clouddata", {"enabled": True})
        return manager

    @pytest.fixture
    def setup_manager_with_failing_dayzero(self):
        manager = PluginManager(config={})
        manager.available_plugins = {
            "mock_dayzero": MockDayzeroPlugin,
            "failing_dayzero": FailingDayzeroPlugin,
        }
        manager.load_plugin("mock_dayzero", {"enabled": True})
        manager.load_plugin("failing_dayzero", {"enabled": True})
        return manager

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_dispatcher_initialization(self, mock_handler, setup_manager_with_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_dayzero)
        assert dispatcher.dispatcher_name == "Dayzero"
        assert len(dispatcher._plugins) > 0

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_success(self, mock_handler, setup_manager_with_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_dayzero)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is True

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_no_plugins(self, mock_handler):
        manager = PluginManager(config={})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_runs_all_plugins(self, mock_handler, setup_manager_with_two_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_two_dayzero)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is True
        plugins = dispatcher.get_active_plugins()
        assert len(plugins) == 2
        plugin_names = [p.name for p in plugins]
        assert "mock_dayzero" in plugin_names
        assert "mock_clouddata" in plugin_names

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_one_fails_returns_false(self, mock_handler, setup_manager_with_failing_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_failing_dayzero)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_returns_false_on_exception(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {"failing_dayzero": FailingDayzeroPlugin}
        manager.load_plugin("failing_dayzero", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_uses_active_plugin(self, mock_handler, setup_manager_with_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_dayzero)
        plugins = dispatcher.get_active_plugins()
        assert len(plugins) > 0
        assert plugins[0].name == "mock_dayzero"

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_runs_plugins_sequentially(self, mock_handler):
        events = []

        class FirstPlugin(DayzeroPlugin):
            name = "zeta_first"
            version = "1.0.0"
            description = "First sequential plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                events.append("first-start")
                await asyncio.sleep(0.01)
                events.append("first-end")
                return True

        class SecondPlugin(DayzeroPlugin):
            name = "alpha_second"
            version = "1.0.0"
            description = "Second sequential plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                events.append("second-start")
                return True

        manager = PluginManager(config={})
        manager.available_plugins = {"zeta_first": FirstPlugin, "alpha_second": SecondPlugin}
        manager.load_plugin("zeta_first", {"enabled": True})
        manager.load_plugin("alpha_second", {"enabled": True})

        dispatcher = DayzeroDispatcher(manager)
        assert asyncio.run(dispatcher.execute("cloud02")) is True
        assert events == ["first-start", "first-end", "second-start"]

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_execute_continues_after_plugin_failure(self, mock_handler):
        events = []

        class FailingPlugin(DayzeroPlugin):
            name = "zeta_failing"
            version = "1.0.0"
            description = "Fails before the second plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                events.append("failing-start")
                raise RuntimeError("boom")

        class SecondPlugin(DayzeroPlugin):
            name = "alpha_second"
            version = "1.0.0"
            description = "Runs after the failing plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                events.append("second-start")
                return True

        manager = PluginManager(config={})
        manager.available_plugins = {"zeta_failing": FailingPlugin, "alpha_second": SecondPlugin}
        manager.load_plugin("zeta_failing", {"enabled": True})
        manager.load_plugin("alpha_second", {"enabled": True})

        dispatcher = DayzeroDispatcher(manager)
        assert asyncio.run(dispatcher.execute("cloud02")) is False
        assert events == ["failing-start", "second-start"]

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_warns_when_cloudcmd_precedes_metadata(self, mock_handler, caplog):
        class CloudCmdPlugin(DayzeroPlugin):
            name = "cloudcmd"
            version = "1.0.0"
            description = "Mock release command plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                return True

        class InstackDataPlugin(DayzeroPlugin):
            name = "instackdata"
            version = "1.0.0"
            description = "Mock metadata plugin"
            author = "Test"

            def initialize(self, plugin_manager=None) -> bool:
                return True

            async def execute(self, cloud: str) -> bool:
                return True

        manager = PluginManager(config={})
        manager.available_plugins = {"cloudcmd": CloudCmdPlugin, "instackdata": InstackDataPlugin}
        manager.load_plugin("cloudcmd", {"enabled": True})
        manager.load_plugin("instackdata", {"enabled": True})

        with caplog.at_level(logging.WARNING):
            DayzeroDispatcher(manager)

        assert "cloudcmd is listed before instackdata" in caplog.text


class TestDayzeroLogHandler:
    """Test that the dayzero log handler targets the BasePlugin loggers"""

    def test_base_plugin_loggers_get_dayzero_handler(self, tmp_path, monkeypatch):
        from quads.plugins.dispatchers import dayzero as dayzero_module

        log_path = tmp_path / "quads-dayzero.log"
        monkeypatch.setattr(dayzero_module, "DAYZERO_LOG", str(log_path))

        names = [
            "quads.plugins.dispatchers.dayzero",
            "quads.plugins.cloudcmd",
            "quads.plugins.clouddata",
            "quads.plugins.instackdata",
            "quads.plugins.builtin.dayzero.cloudcmd",
        ]
        before_handlers = {name: list(logging.getLogger(name).handlers) for name in names}
        before_levels = {name: logging.getLogger(name).level for name in names}

        try:
            dayzero_module._ensure_dayzero_log_handler()

            for name in names[:-1]:
                handlers = logging.getLogger(name).handlers
                assert any(
                    isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path)
                    for handler in handlers
                )

            assert not any(
                isinstance(handler, logging.FileHandler) and handler.baseFilename == str(log_path)
                for handler in logging.getLogger(names[-1]).handlers
            )
        finally:
            for name in names:
                target = logging.getLogger(name)
                for handler in list(target.handlers):
                    if handler not in before_handlers[name]:
                        target.removeHandler(handler)
                        handler.close()
                target.setLevel(before_levels[name])


class TestCloudCmdPlugin:
    """Test CloudCmdPlugin"""

    def test_metadata(self):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        assert CloudCmdPlugin.name == "cloudcmd"
        assert CloudCmdPlugin.version == "1.0.0"
        assert CloudCmdPlugin.run_mode == "per_cloud"

    def test_initialize(self):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.logger = MagicMock()
        assert plugin.initialize() is True

    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_no_command_set(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_assignment.owner = "testuser"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = None
        mock_api.get_user.return_value = mock_user

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True
        plugin.logger.info.assert_called()

    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_no_active_assignment(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_api.get_active_cloud_assignment.return_value = None

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True

    @patch("quads.plugins.builtin.dayzero.cloudcmd.asyncio.create_subprocess_exec")
    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_ssh_success(self, mock_api_cls, mock_subprocess):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_assignment.owner = "testuser"
        mock_assignment.id = 1
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = "echo hello"
        mock_api.get_user.return_value = mock_user

        mock_schedule = MagicMock()
        mock_schedule.host.name = "host01.example.com"
        mock_api.get_current_schedules.return_value = [mock_schedule]

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is True
        mock_subprocess.assert_called_once()
        ssh_args = mock_subprocess.call_args[0]
        assert "root@host01.example.com" in ssh_args
        assert any("tmux" in str(a) for a in ssh_args)

    @patch("quads.plugins.builtin.dayzero.cloudcmd.asyncio.create_subprocess_exec")
    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_ssh_failure(self, mock_api_cls, mock_subprocess):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_assignment.owner = "testuser"
        mock_assignment.id = 1
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = "echo hello"
        mock_api.get_user.return_value = mock_user

        mock_schedule = MagicMock()
        mock_schedule.host.name = "host01.example.com"
        mock_api.get_current_schedules.return_value = [mock_schedule]

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Connection refused")
        mock_proc.returncode = 255
        mock_subprocess.return_value = mock_proc

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute("cloud02"))
        assert result is False


class TestDayzeroDiscovery:
    """Test that dayzero plugins are discoverable"""

    def test_discovery_includes_dayzero_path(self):
        from quads.plugins.discovery import PluginDiscovery

        discovery = PluginDiscovery()
        assert "quads.plugins.builtin.dayzero" in discovery.builtin_paths

    def test_cloudcmd_discovered(self):
        from quads.plugins.discovery import PluginDiscovery
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("quads.plugins.builtin.dayzero")
        assert "cloudcmd" in plugins
        assert plugins["cloudcmd"] is CloudCmdPlugin
