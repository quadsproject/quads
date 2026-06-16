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
    MockDayzeroCloudPlugin,
    FailingDayzeroPlugin,
    FailingDayzeroCloudPlugin,
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

            async def execute(self, host, cloud):
                return True

        plugin = CompleteDayzeroPlugin({})
        assert plugin is not None
        result = asyncio.run(plugin.execute("host01.example.com", "cloud02"))
        assert result is True

    def test_default_run_mode_is_per_cloud(self):
        class SimpleDayzeroPlugin(DayzeroPlugin):
            name = "simple"

            async def execute(self, host, cloud):
                return True

        plugin = SimpleDayzeroPlugin({})
        assert plugin.run_mode == "per_cloud"

    def test_per_host_run_mode(self):
        class HostDayzeroPlugin(DayzeroPlugin):
            name = "host_plugin"
            run_mode = "per_host"

            async def execute(self, host, cloud):
                return True

        plugin = HostDayzeroPlugin({})
        assert plugin.run_mode == "per_host"


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
    def test_run_dayzero_success(self, mock_handler, setup_manager_with_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_dayzero)
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02"))
        assert isinstance(result, dict)
        assert result.get("mock_dayzero") is True

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_no_plugins(self, mock_handler):
        manager = PluginManager(config={})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02"))
        assert result == {}

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_nonfatal_on_failure(self, mock_handler, setup_manager_with_failing_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_failing_dayzero)
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02"))
        assert isinstance(result, dict)
        assert result.get("mock_dayzero") is True
        assert result.get("failing_dayzero") is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_only_dispatches_per_host_plugins(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {
            "mock_dayzero": MockDayzeroPlugin,
            "mock_dayzero_cloud": MockDayzeroCloudPlugin,
        }
        manager.load_plugin("mock_dayzero", {"enabled": True})
        manager.load_plugin("mock_dayzero_cloud", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02"))
        assert "mock_dayzero" in result
        assert "mock_dayzero_cloud" not in result

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_success(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {
            "mock_dayzero": MockDayzeroPlugin,
            "mock_dayzero_cloud": MockDayzeroCloudPlugin,
        }
        manager.load_plugin("mock_dayzero", {"enabled": True})
        manager.load_plugin("mock_dayzero_cloud", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        hosts = ["host01.example.com", "host02.example.com"]
        result = asyncio.run(dispatcher.run_dayzero_cloud(hosts, "cloud02"))
        assert "mock_dayzero_cloud" in result
        assert result.get("mock_dayzero_cloud") is True
        assert "mock_dayzero" not in result

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_no_plugins(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {"mock_dayzero": MockDayzeroPlugin}
        manager.load_plugin("mock_dayzero", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero_cloud(["host01.example.com"], "cloud02"))
        assert result == {}

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_nonfatal_on_failure(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {
            "mock_dayzero_cloud": MockDayzeroCloudPlugin,
            "failing_dayzero_cloud": FailingDayzeroCloudPlugin,
        }
        manager.load_plugin("mock_dayzero_cloud", {"enabled": True})
        manager.load_plugin("failing_dayzero_cloud", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        hosts = ["host01.example.com", "host02.example.com"]
        result = asyncio.run(dispatcher.run_dayzero_cloud(hosts, "cloud02"))
        assert isinstance(result, dict)
        assert result.get("mock_dayzero_cloud") is True
        assert result.get("failing_dayzero_cloud") is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_empty_hosts(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {"mock_dayzero_cloud": MockDayzeroCloudPlugin}
        manager.load_plugin("mock_dayzero_cloud", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero_cloud([], "cloud02"))
        assert isinstance(result, dict)


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
        result = asyncio.run(plugin.execute(["host01.example.com"], "cloud02"))
        assert result is True
        plugin.logger.info.assert_called()

    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_first_host_selection(self, mock_api_cls):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_assignment.owner = "testuser"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = "echo hello"
        mock_api.get_user.return_value = mock_user

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()

        hosts = ["f03-h30.example.com", "f01-h10.example.com", "f02-h20.example.com"]
        with patch.object(plugin, "_ssh_exec", new_callable=AsyncMock) as mock_ssh:
            mock_ssh.return_value = True
            asyncio.run(plugin.execute(hosts, "cloud02"))
            call_args = mock_ssh.call_args
            assert call_args[0][0] == "f01-h10.example.com"

    @patch("quads.plugins.builtin.dayzero.cloudcmd.asyncio.create_subprocess_exec")
    @patch("quads.plugins.builtin.dayzero.cloudcmd.QuadsApi")
    def test_ssh_success(self, mock_api_cls, mock_subprocess):
        from quads.plugins.builtin.dayzero.cloudcmd import CloudCmdPlugin

        mock_api = MagicMock()
        mock_api_cls.return_value = mock_api
        mock_assignment = MagicMock()
        mock_assignment.owner = "testuser"
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = "echo hello"
        mock_api.get_user.return_value = mock_user

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute(["host01.example.com"], "cloud02"))
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
        mock_api.get_active_cloud_assignment.return_value = mock_assignment
        mock_user = MagicMock()
        mock_user.release_command = "echo hello"
        mock_api.get_user.return_value = mock_user

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Connection refused")
        mock_proc.returncode = 255
        mock_subprocess.return_value = mock_proc

        plugin = CloudCmdPlugin({"enabled": True})
        plugin.initialize()
        plugin.logger = MagicMock()
        result = asyncio.run(plugin.execute(["host01.example.com"], "cloud02"))
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
