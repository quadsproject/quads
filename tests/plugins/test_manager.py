"""Tests for plugin manager"""

from unittest.mock import MagicMock, patch

from quads.plugins.manager import PluginManager
from tests.plugins.conftest import (
    MockChatPlugin,
    MockEmailPlugin,
    FailingPlugin,
    ExceptionPlugin,
)


class TestPluginManager:
    """Test cases for PluginManager class"""

    def test_manager_initialization(self):
        """Test that manager initializes correctly"""
        config = {"plugins": {}}
        manager = PluginManager(config=config)
        # When config is provided, it should be used
        assert manager.config == config
        assert manager.available_plugins == {}
        assert manager.loaded_plugins == {}

    def test_manager_initialization_with_config(self):
        """Test that manager initializes with provided config"""
        config = {"plugins": {"test": {"enabled": True}}}
        manager = PluginManager(config=config)
        assert manager.config == config

    def test_manager_initialization_without_config(self):
        """Test that manager can initialize without config"""
        with patch("quads.plugins.manager.Config", {}):
            manager = PluginManager()
            assert manager.config is not None

    @patch("quads.plugins.manager.PluginDiscovery")
    def test_initialize_discovers_plugins(self, mock_discovery_class):
        """Test that initialize discovers available plugins"""
        mock_discovery = MagicMock()
        mock_discovery.discover_plugins.return_value = {
            "mock_chat": MockChatPlugin,
            "mock_email": MockEmailPlugin,
        }
        mock_discovery_class.return_value = mock_discovery

        manager = PluginManager(config={})
        manager.initialize()

        assert "mock_chat" in manager.available_plugins
        assert "mock_email" in manager.available_plugins
        mock_discovery.discover_plugins.assert_called_once()

    @patch("quads.plugins.manager.PluginDiscovery")
    def test_initialize_loads_enabled_plugins(self, mock_discovery_class):
        """Test that initialize loads enabled plugins from config"""
        mock_discovery = MagicMock()
        mock_discovery.discover_plugins.return_value = {
            "mock_chat": MockChatPlugin,
        }
        mock_discovery_class.return_value = mock_discovery

        config = {
            "plugins": {
                "mock_chat": {"enabled": True, "webhook_url": "https://example.com"},
            }
        }
        manager = PluginManager(config=config)
        manager.initialize()

        assert "mock_chat" in manager.loaded_plugins
        assert isinstance(manager.loaded_plugins["mock_chat"], MockChatPlugin)

    @patch("quads.plugins.manager.PluginDiscovery")
    def test_initialize_skips_disabled_plugins(self, mock_discovery_class):
        """Test that initialize skips disabled plugins"""
        mock_discovery = MagicMock()
        mock_discovery.discover_plugins.return_value = {
            "mock_chat": MockChatPlugin,
        }
        mock_discovery_class.return_value = mock_discovery

        config = {
            "plugins": {
                "mock_chat": {"enabled": False},
            }
        }
        manager = PluginManager(config=config)
        manager.initialize()

        assert "mock_chat" not in manager.loaded_plugins

    def test_load_plugin_not_found(self, plugin_manager, caplog):
        """Test loading a plugin that doesn't exist"""
        result = plugin_manager.load_plugin("nonexistent", {})
        assert result is None
        assert "Plugin nonexistent not found" in caplog.text

    def test_load_plugin_success(self, plugin_manager):
        """Test successful plugin loading"""
        plugin_manager.available_plugins = {"mock_chat": MockChatPlugin}
        config = {"enabled": True}

        result = plugin_manager.load_plugin("mock_chat", config)

        assert result is not None
        assert isinstance(result, MockChatPlugin)
        assert "mock_chat" in plugin_manager.loaded_plugins

    def test_load_plugin_initialization_failure(self, plugin_manager, caplog):
        """Test plugin that fails to initialize"""
        plugin_manager.available_plugins = {"failing": FailingPlugin}
        config = {"enabled": True}

        result = plugin_manager.load_plugin("failing", config)

        assert result is None
        assert "failing" not in plugin_manager.loaded_plugins
        assert "failed to initialize" in caplog.text

    def test_load_plugin_exception(self, plugin_manager, caplog):
        """Test plugin that raises exception during initialization"""
        plugin_manager.available_plugins = {"exception": ExceptionPlugin}
        config = {"enabled": True}

        result = plugin_manager.load_plugin("exception", config)

        assert result is None
        assert "exception" not in plugin_manager.loaded_plugins
        assert "Error loading plugin exception" in caplog.text

    def test_get_plugin_success(self, plugin_manager):
        """Test getting a loaded plugin by name"""
        plugin_manager.available_plugins = {"mock_chat": MockChatPlugin}
        config = {"enabled": True}
        plugin_manager.load_plugin("mock_chat", config)

        result = plugin_manager.get_plugin("mock_chat")

        assert result is not None
        assert isinstance(result, MockChatPlugin)

    def test_get_plugin_with_type_filter(self, plugin_manager):
        """Test getting a plugin with type filtering"""
        plugin_manager.available_plugins = {
            "mock_chat": MockChatPlugin,
            "mock_email": MockEmailPlugin,
        }
        plugin_manager.load_plugin("mock_chat", {"enabled": True})
        plugin_manager.load_plugin("mock_email", {"enabled": True})

        from quads.plugins.interfaces.chat import ChatPlugin

        result = plugin_manager.get_plugin("mock_chat", ChatPlugin)

        assert result is not None
        assert isinstance(result, ChatPlugin)

    def test_get_plugin_wrong_type(self, plugin_manager):
        """Test getting a plugin with wrong type filter"""
        plugin_manager.available_plugins = {"mock_email": MockEmailPlugin}
        plugin_manager.load_plugin("mock_email", {"enabled": True})

        from quads.plugins.interfaces.chat import ChatPlugin

        result = plugin_manager.get_plugin("mock_email", ChatPlugin)

        assert result is None

    def test_get_plugin_not_loaded(self, plugin_manager):
        """Test getting a plugin that isn't loaded"""
        result = plugin_manager.get_plugin("nonexistent")
        assert result is None

    def test_get_plugins_by_type(self, plugin_manager):
        """Test getting all plugins of a specific type"""
        from quads.plugins.interfaces.chat import ChatPlugin
        from quads.plugins.interfaces.email import EmailPlugin

        plugin_manager.available_plugins = {
            "mock_chat": MockChatPlugin,
            "mock_email": MockEmailPlugin,
        }
        plugin_manager.load_plugin("mock_chat", {"enabled": True})
        plugin_manager.load_plugin("mock_email", {"enabled": True})

        chat_plugins = plugin_manager.get_plugins_by_type(ChatPlugin)
        email_plugins = plugin_manager.get_plugins_by_type(EmailPlugin)

        assert len(chat_plugins) == 1
        assert isinstance(chat_plugins[0], ChatPlugin)
        assert len(email_plugins) == 1
        assert isinstance(email_plugins[0], EmailPlugin)

    def test_get_plugins_by_type_empty(self, plugin_manager):
        """Test getting plugins by type when none are loaded"""
        from quads.plugins.interfaces.chat import ChatPlugin

        plugins = plugin_manager.get_plugins_by_type(ChatPlugin)
        assert len(plugins) == 0

    def test_multiple_plugins_same_type(self, plugin_manager):
        """Test loading multiple plugins of the same type"""
        from quads.plugins.interfaces.chat import ChatPlugin

        class AnotherChatPlugin(ChatPlugin):
            name = "another_chat"
            version = "1.0.0"

            def initialize(self, plugin_manager=None):
                return True

            async def send_message(self, message, channels=None, **kwargs):
                return True

        plugin_manager.available_plugins = {
            "mock_chat": MockChatPlugin,
            "another_chat": AnotherChatPlugin,
        }
        plugin_manager.load_plugin("mock_chat", {"enabled": True})
        plugin_manager.load_plugin("another_chat", {"enabled": True})

        chat_plugins = plugin_manager.get_plugins_by_type(ChatPlugin)
        assert len(chat_plugins) == 2

    def test_plugin_config_passed_to_instance(self, plugin_manager):
        """Test that plugin config is passed correctly to instance"""
        plugin_manager.available_plugins = {"mock_chat": MockChatPlugin}
        config = {"enabled": True, "webhook_url": "https://test.com", "custom_param": "value"}

        plugin = plugin_manager.load_plugin("mock_chat", config)

        assert plugin.config == config
        assert plugin.config.get("webhook_url") == "https://test.com"
        assert plugin.config.get("custom_param") == "value"
