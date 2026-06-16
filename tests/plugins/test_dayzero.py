"""Tests for dayzero plugin system"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from quads.plugins.base import BasePlugin
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.dispatchers.dayzero import DayzeroDispatcher
from quads.plugins.builtin.dayzero.runonce.moveinfo import MoveInfoPlugin
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

            async def execute(self, host, cloud, schedule_data):
                return True

        plugin = CompleteDayzeroPlugin({})
        assert plugin is not None
        result = asyncio.run(plugin.execute("host01.example.com", "cloud02", {"stage_timestamps": {}}))
        assert result is True

    def test_default_run_mode_is_per_host(self):
        class SimpleDayzeroPlugin(DayzeroPlugin):
            name = "simple"

            async def execute(self, host, cloud, schedule_data):
                return True

        plugin = SimpleDayzeroPlugin({})
        assert plugin.run_mode == "per_host"

    def test_per_cloud_run_mode(self):
        class CloudDayzeroPlugin(DayzeroPlugin):
            name = "cloud_plugin"
            run_mode = "per_cloud"

            async def execute(self, host, cloud, schedule_data):
                return True

        plugin = CloudDayzeroPlugin({})
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
    def test_run_dayzero_success(self, mock_handler, setup_manager_with_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_dayzero)
        schedule_data = {"stage_timestamps": {"pending": "2026-06-16T10:00:00"}}
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02", schedule_data))
        assert isinstance(result, dict)
        assert result.get("mock_dayzero") is True

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_no_plugins(self, mock_handler):
        manager = PluginManager(config={})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02", {}))
        assert result == {}

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_nonfatal_on_failure(self, mock_handler, setup_manager_with_failing_dayzero):
        dispatcher = DayzeroDispatcher(setup_manager_with_failing_dayzero)
        schedule_data = {"stage_timestamps": {}}
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02", schedule_data))
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
        result = asyncio.run(dispatcher.run_dayzero("host01.example.com", "cloud02", {}))
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
        schedule_data_list = [{"stage_timestamps": {}}, {"stage_timestamps": {}}]
        result = asyncio.run(dispatcher.run_dayzero_cloud(hosts, "cloud02", schedule_data_list))
        assert "mock_dayzero_cloud" in result
        assert result.get("mock_dayzero_cloud") is True
        assert "mock_dayzero" not in result

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_no_plugins(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {"mock_dayzero": MockDayzeroPlugin}
        manager.load_plugin("mock_dayzero", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero_cloud(["host01.example.com"], "cloud02", [{}]))
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
        result = asyncio.run(dispatcher.run_dayzero_cloud(hosts, "cloud02", [{}, {}]))
        assert isinstance(result, dict)
        assert result.get("mock_dayzero_cloud") is True
        assert result.get("failing_dayzero_cloud") is False

    @patch("quads.plugins.dispatchers.dayzero._ensure_dayzero_log_handler")
    def test_run_dayzero_cloud_empty_hosts(self, mock_handler):
        manager = PluginManager(config={})
        manager.available_plugins = {"mock_dayzero_cloud": MockDayzeroCloudPlugin}
        manager.load_plugin("mock_dayzero_cloud", {"enabled": True})
        dispatcher = DayzeroDispatcher(manager)
        result = asyncio.run(dispatcher.run_dayzero_cloud([], "cloud02", []))
        assert isinstance(result, dict)


class TestMoveInfoPlugin:
    """Test MoveInfoPlugin"""

    def test_metadata(self):
        assert MoveInfoPlugin.name == "moveinfo"
        assert MoveInfoPlugin.version == "1.0.0"
        assert MoveInfoPlugin.author == "QUADS Team"
        assert MoveInfoPlugin.run_mode == "per_host"

    def test_initialize(self):
        plugin = MoveInfoPlugin({"enabled": True})
        plugin.logger = MagicMock()
        assert plugin.initialize() is True

    def test_build_content(self):
        plugin = MoveInfoPlugin({"enabled": True})
        timestamps = {
            "pending": "2026-06-16T10:00:00",
            "switch_config": "2026-06-16T10:01:30",
            "released": "2026-06-16T10:28:00",
        }
        content = plugin._build_content("host01.example.com", "cloud02", timestamps)

        assert "QUADS Deployment Info" in content
        assert "Host: host01.example.com" in content
        assert "Cloud: cloud02" in content
        assert "01. pending" in content
        assert "2026-06-16T10:00:00" in content
        assert "12. released" in content
        assert "2026-06-16T10:28:00" in content
        assert "N/A" in content

    def test_build_content_empty_timestamps(self):
        plugin = MoveInfoPlugin({"enabled": True})
        content = plugin._build_content("host01.example.com", "cloud02", {})
        assert content.count("N/A") == 12

    @patch("quads.plugins.builtin.dayzero.runonce.moveinfo.asyncio.create_subprocess_exec")
    def test_execute_success(self, mock_subprocess):
        plugin = MoveInfoPlugin({"enabled": True})
        plugin.logger = MagicMock()

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"")
        mock_proc.returncode = 0
        mock_subprocess.return_value = mock_proc

        schedule_data = {
            "stage_timestamps": {"pending": "2026-06-16T10:00:00"},
        }
        result = asyncio.run(plugin.execute("host01.example.com", "cloud02", schedule_data))
        assert result is True
        mock_subprocess.assert_called_once()

    @patch("quads.plugins.builtin.dayzero.runonce.moveinfo.asyncio.create_subprocess_exec")
    def test_execute_ssh_failure(self, mock_subprocess):
        plugin = MoveInfoPlugin({"enabled": True})
        plugin.logger = MagicMock()

        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (b"", b"Connection refused")
        mock_proc.returncode = 255
        mock_subprocess.return_value = mock_proc

        result = asyncio.run(plugin.execute("host01.example.com", "cloud02", {"stage_timestamps": {}}))
        assert result is False
        plugin.logger.error.assert_called()


class TestStageTimestamps:
    """Test per-stage timestamp recording on Schedule model"""

    def test_record_stage_timestamp_empty(self):
        from quads.server.models import Schedule

        schedule = Schedule()
        schedule.move_stage_timestamps = None
        schedule.record_stage_timestamp("pending")
        timestamps = json.loads(schedule.move_stage_timestamps)
        assert "pending" in timestamps

    def test_record_stage_timestamp_accumulates(self):
        from quads.server.models import Schedule

        schedule = Schedule()
        schedule.move_stage_timestamps = None
        schedule.record_stage_timestamp("pending")
        schedule.record_stage_timestamp("switch_config")
        schedule.record_stage_timestamp("ipmi_config")
        timestamps = json.loads(schedule.move_stage_timestamps)
        assert len(timestamps) == 3
        assert "pending" in timestamps
        assert "switch_config" in timestamps
        assert "ipmi_config" in timestamps

    def test_record_stage_timestamp_preserves_existing(self):
        from quads.server.models import Schedule

        schedule = Schedule()
        schedule.move_stage_timestamps = json.dumps({"pending": "2026-06-16T10:00:00"})
        schedule.record_stage_timestamp("switch_config")
        timestamps = json.loads(schedule.move_stage_timestamps)
        assert timestamps["pending"] == "2026-06-16T10:00:00"
        assert "switch_config" in timestamps

    def test_record_stage_timestamp_handles_malformed_json(self):
        from quads.server.models import Schedule

        schedule = Schedule()
        schedule.move_stage_timestamps = "not valid json{{"
        schedule.record_stage_timestamp("pending")
        timestamps = json.loads(schedule.move_stage_timestamps)
        assert "pending" in timestamps

    def test_record_stage_timestamp_handles_empty_string(self):
        from quads.server.models import Schedule

        schedule = Schedule()
        schedule.move_stage_timestamps = ""
        schedule.record_stage_timestamp("pending")
        timestamps = json.loads(schedule.move_stage_timestamps)
        assert "pending" in timestamps


class TestDayzeroDiscovery:
    """Test that dayzero plugins are discoverable"""

    def test_discovery_includes_dayzero_paths(self):
        from quads.plugins.discovery import PluginDiscovery

        discovery = PluginDiscovery()
        assert "quads.plugins.builtin.dayzero.runonce" in discovery.builtin_paths
        assert "quads.plugins.builtin.dayzero.runonce.contrib" in discovery.builtin_paths

    def test_moveinfo_discovered(self):
        from quads.plugins.discovery import PluginDiscovery

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("quads.plugins.builtin.dayzero.runonce")
        assert "moveinfo" in plugins
        assert plugins["moveinfo"] is MoveInfoPlugin
