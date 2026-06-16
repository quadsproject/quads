"""Tests for dayzero plugin system"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from quads.plugins.base import BasePlugin
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.dispatchers.dayzero import DayzeroDispatcher
from quads.plugins.manager import PluginManager
from tests.plugins.conftest import (
    MockDayzeroPlugin,
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
    def test_execute_with_failing_plugin_uses_first(self, mock_handler, setup_manager_with_failing_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_failing_dayzero)
        result = asyncio.run(dispatcher.execute("cloud02"))
        assert result is True
        assert dispatcher.get_active_plugin().name == "mock_dayzero"

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
        plugin = dispatcher.get_active_plugin()
        assert plugin is not None
        assert plugin.name == "mock_dayzero"


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
        mock_api.get_schedules.return_value = [mock_schedule]

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
        mock_api.get_schedules.return_value = [mock_schedule]

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
