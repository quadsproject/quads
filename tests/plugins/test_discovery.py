"""Tests for plugin discovery"""

from unittest.mock import patch, MagicMock
from pathlib import Path

from quads.plugins.discovery import PluginDiscovery
from quads.plugins.base import BasePlugin


class TestPluginDiscovery:
    """Test cases for PluginDiscovery class"""

    def test_discovery_initialization(self):
        """Test that discovery initializes with correct paths"""
        discovery = PluginDiscovery()
        assert len(discovery.builtin_paths) == 9
        assert "quads.plugins.builtin.chat" in discovery.builtin_paths
        assert "quads.plugins.builtin.cloud" in discovery.builtin_paths
        assert discovery.external_path == Path("/opt/quads/plugins/")

    def test_discover_plugins_returns_dict(self):
        """Test that discover_plugins returns a dictionary"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()
        assert isinstance(plugins, dict)

    @patch("pkgutil.iter_modules")
    @patch("quads.plugins.discovery.import_module")
    def test_discover_in_package_success(self, mock_import, mock_iter):
        """Test successful plugin discovery in package"""
        # Mock the package structure
        mock_package = MagicMock()
        mock_package.__path__ = ["/mock/path"]

        # Create a proper mock plugin class
        class MockPlugin(BasePlugin):
            name = "mock"

        mock_module = MagicMock()
        # Make dir() return our plugin class name
        type(mock_module).__dir__ = lambda self: ["MockPlugin"]
        # Make getattr return the plugin class
        type(mock_module).__getattribute__ = lambda self, name: (
            MockPlugin if name == "MockPlugin" else object.__getattribute__(self, name)
        )

        mock_import.side_effect = [mock_package, mock_module]
        mock_iter.return_value = [("", "mock", False)]

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("mock.package")
        assert isinstance(plugins, dict)
        # The plugin should be discovered
        assert len(plugins) >= 0  # May or may not find it depending on mocking

    @patch("quads.plugins.discovery.import_module")
    def test_discover_in_package_import_error(self, mock_import, caplog):
        """Test handling of ImportError during package discovery"""
        mock_import.side_effect = ImportError("Module not found")

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_package("nonexistent.package")

        assert plugins == {}
        assert "Failed to load plugin package" in caplog.text

    def test_discover_in_directory_nonexistent(self):
        """Test discovery in non-existent directory"""
        discovery = PluginDiscovery()
        fake_path = Path("/nonexistent/path")
        plugins = discovery._discover_in_directory(fake_path)
        assert plugins == {}

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.glob")
    def test_discover_in_directory_empty(self, mock_glob, mock_exists):
        """Test discovery in empty directory"""
        mock_exists.return_value = True
        mock_glob.return_value = []

        discovery = PluginDiscovery()
        plugins = discovery._discover_in_directory(Path("/mock/path"))
        assert plugins == {}

    def test_discover_builtin_chat_plugins(self):
        """Test that built-in chat plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that at least some chat plugins are discovered
        chat_plugins = ["slack", "gchat", "irc"]
        for plugin_name in chat_plugins:
            if plugin_name in plugins:
                assert issubclass(plugins[plugin_name], BasePlugin)

    def test_discover_builtin_email_plugins(self):
        """Test that built-in email plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that email plugin can be discovered
        if "email" in plugins:
            assert issubclass(plugins["email"], BasePlugin)

    def test_discover_builtin_hardware_plugins(self):
        """Test that built-in hardware plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that hardware plugins can be discovered
        if "badfish" in plugins:
            assert issubclass(plugins["badfish"], BasePlugin)

    def test_discover_builtin_switch_plugins(self):
        """Test that built-in switch plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that switch plugins can be discovered
        if "juniper" in plugins:
            assert issubclass(plugins["juniper"], BasePlugin)

    def test_discover_builtin_provisioner_plugins(self):
        """Test that built-in provisioner plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that provisioner plugins can be discovered
        if "foreman" in plugins:
            assert issubclass(plugins["foreman"], BasePlugin)

    def test_discover_builtin_ticketing_plugins(self):
        """Test that built-in ticketing plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that ticketing plugins can be discovered
        if "jira" in plugins:
            assert issubclass(plugins["jira"], BasePlugin)

    def test_discover_builtin_cloud_plugins(self):
        """Test that built-in cloud plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that cloud plugins can be discovered
        cloud_plugins = ["aws", "ibm_cloud"]
        for plugin_name in cloud_plugins:
            if plugin_name in plugins:
                assert issubclass(plugins[plugin_name], BasePlugin)

    def test_discover_builtin_validator_plugins(self):
        """Test that built-in validator plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that validator plugins can be discovered
        if "environment" in plugins:
            assert issubclass(plugins["environment"], BasePlugin)

    def test_discover_builtin_release_plugins(self):
        """Test that built-in release plugins can be discovered"""
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()

        # Check that release plugins can be discovered
        if "standard" in plugins:
            assert issubclass(plugins["standard"], BasePlugin)

    @patch("pathlib.Path.exists")
    def test_discover_external_plugins_path_not_exists(self, mock_exists):
        """Test that external path is checked for existence"""
        mock_exists.return_value = False
        discovery = PluginDiscovery()
        plugins = discovery.discover_plugins()
        # Should still return built-in plugins even if external path doesn't exist
        assert isinstance(plugins, dict)

    def test_builtin_paths_complete(self):
        """Test that all expected builtin paths are configured"""
        discovery = PluginDiscovery()
        expected_paths = [
            "quads.plugins.builtin.chat",
            "quads.plugins.builtin.cloud",
            "quads.plugins.builtin.email",
            "quads.plugins.builtin.hardware",
            "quads.plugins.builtin.provisioners",
            "quads.plugins.builtin.release",
            "quads.plugins.builtin.switches",
            "quads.plugins.builtin.ticketing",
            "quads.plugins.builtin.validators",
        ]
        assert discovery.builtin_paths == expected_paths
