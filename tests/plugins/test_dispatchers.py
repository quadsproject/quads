"""Tests for plugin dispatchers"""

import pytest
from unittest.mock import patch

from quads.plugins.dispatchers.base import BaseDispatcher
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.interfaces.email import EmailPlugin
from tests.plugins.conftest import MockChatPlugin, MockEmailPlugin


class AnotherChatPlugin(ChatPlugin):
    """Another mock chat plugin for multi-plugin testing"""

    name = "another_chat"
    version = "1.0.0"
    description = "Another chat plugin"
    author = "Test"

    def initialize(self, plugin_manager=None) -> bool:
        return True

    async def send_message(self, message: str, channels=None, **kwargs) -> bool:
        return True


class TestBaseDispatcher:
    """Test cases for BaseDispatcher class"""

    @pytest.fixture
    def setup_manager_with_chat_plugins(self, plugin_manager):
        """Setup plugin manager with multiple chat plugins"""
        plugin_manager.available_plugins = {
            "mock_chat": MockChatPlugin,
            "another_chat": AnotherChatPlugin,
        }
        plugin_manager.load_plugin("mock_chat", {"enabled": True})
        plugin_manager.load_plugin("another_chat", {"enabled": True})
        return plugin_manager

    @pytest.fixture
    def setup_manager_with_mixed_plugins(self, plugin_manager):
        """Setup plugin manager with chat and email plugins"""
        plugin_manager.available_plugins = {
            "mock_chat": MockChatPlugin,
            "mock_email": MockEmailPlugin,
        }
        plugin_manager.load_plugin("mock_chat", {"enabled": True})
        plugin_manager.load_plugin("mock_email", {"enabled": True})
        return plugin_manager

    def test_dispatcher_initialization(self, setup_manager_with_chat_plugins):
        """Test dispatcher initialization"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert dispatcher.plugin_manager == manager
        assert dispatcher.plugin_type == ChatPlugin
        assert dispatcher.dispatcher_name == "Chat"
        assert len(dispatcher._plugins) == 2

    def test_dispatcher_default_plugin_selection(self, setup_manager_with_chat_plugins):
        """Test that first enabled plugin becomes default"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        default_plugin = dispatcher.get_default_plugin()
        assert default_plugin is not None
        assert isinstance(default_plugin, ChatPlugin)
        # First loaded plugin should be default
        assert default_plugin.name == "mock_chat"

    def test_dispatcher_no_plugins_available(self, plugin_manager):
        """Test dispatcher when no plugins of type are available"""
        # Don't load any plugins
        dispatcher = BaseDispatcher(
            plugin_manager=plugin_manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert len(dispatcher._plugins) == 0
        assert dispatcher.get_default_plugin() is None

    def test_dispatcher_get_plugin_by_name(self, setup_manager_with_chat_plugins):
        """Test getting a specific plugin by name"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        plugin = dispatcher.get_plugin_by_name("another_chat")
        assert plugin is not None
        assert plugin.name == "another_chat"

    def test_dispatcher_get_plugin_by_name_not_found(self, setup_manager_with_chat_plugins):
        """Test getting a plugin that doesn't exist"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        plugin = dispatcher.get_plugin_by_name("nonexistent")
        assert plugin is None

    def test_dispatcher_specific_plugin_selection(self, setup_manager_with_chat_plugins):
        """Test selecting a specific plugin as default"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
            plugin_name="another_chat",
        )

        default_plugin = dispatcher.get_default_plugin()
        assert default_plugin.name == "another_chat"

    def test_dispatcher_invalid_plugin_selection_raises_error(self, setup_manager_with_chat_plugins):
        """Test that selecting non-existent plugin raises error"""
        manager = setup_manager_with_chat_plugins

        with pytest.raises(ValueError, match="Plugin 'nonexistent' not found"):
            BaseDispatcher(
                plugin_manager=manager,
                plugin_type=ChatPlugin,
                dispatcher_name="Chat",
                plugin_name="nonexistent",
            )

    def test_dispatcher_filters_by_plugin_type(self, setup_manager_with_mixed_plugins):
        """Test that dispatcher only loads plugins of specified type"""
        manager = setup_manager_with_mixed_plugins
        chat_dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        # Should only have chat plugins
        assert len(chat_dispatcher._plugins) == 1
        assert all(isinstance(p, ChatPlugin) for p in chat_dispatcher._plugins)

        email_dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=EmailPlugin,
            dispatcher_name="Email",
        )

        # Should only have email plugins
        assert len(email_dispatcher._plugins) == 1
        assert all(isinstance(p, EmailPlugin) for p in email_dispatcher._plugins)

    def test_dispatcher_multiple_plugin_names_filter(self, setup_manager_with_chat_plugins):
        """Test filtering to multiple specific plugin names"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
            plugin_names=["mock_chat", "another_chat"],
        )

        # All specified plugins should be available
        assert dispatcher.get_plugin_by_name("mock_chat") is not None
        assert dispatcher.get_plugin_by_name("another_chat") is not None

    def test_dispatcher_plugin_names_invalid_raises_error(self, setup_manager_with_chat_plugins):
        """Test that invalid plugin name in filter raises error"""
        manager = setup_manager_with_chat_plugins

        with pytest.raises(ValueError, match="Plugin 'invalid' not found"):
            BaseDispatcher(
                plugin_manager=manager,
                plugin_type=ChatPlugin,
                dispatcher_name="Chat",
                plugin_names=["mock_chat", "invalid"],
            )

    def test_dispatcher_refresh_plugins(self, setup_manager_with_chat_plugins):
        """Test that dispatcher can refresh its plugin list"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        initial_count = len(dispatcher._plugins)
        assert initial_count == 2

        # Refresh should maintain the plugin list
        dispatcher._refresh_plugins()
        assert len(dispatcher._plugins) == initial_count

    def test_dispatcher_default_plugin_class_stored(self, setup_manager_with_chat_plugins):
        """Test that dispatcher stores default plugin class"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert dispatcher._default_plugin_class is not None
        assert dispatcher._default_plugin_class == MockChatPlugin

    def test_dispatcher_logging_on_init(self, setup_manager_with_chat_plugins, caplog):
        """Test that dispatcher logs plugin loading"""
        import logging

        caplog.set_level(logging.INFO)

        manager = setup_manager_with_chat_plugins
        BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert "Chat dispatcher loaded 2 plugins" in caplog.text
        assert "mock_chat" in caplog.text
        assert "another_chat" in caplog.text

    def test_dispatcher_logging_no_plugins(self, plugin_manager, caplog):
        """Test that dispatcher logs warning when no plugins available"""
        BaseDispatcher(
            plugin_manager=plugin_manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert "No Chat plugins are enabled" in caplog.text

    def test_dispatcher_with_single_plugin(self, plugin_manager):
        """Test dispatcher with only one plugin loaded"""
        plugin_manager.available_plugins = {"mock_chat": MockChatPlugin}
        plugin_manager.load_plugin("mock_chat", {"enabled": True})

        dispatcher = BaseDispatcher(
            plugin_manager=plugin_manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        assert len(dispatcher._plugins) == 1
        assert dispatcher.get_default_plugin().name == "mock_chat"

    def test_dispatcher_plugin_enabled_check(self, setup_manager_with_chat_plugins):
        """Test that only enabled plugins are included"""
        manager = setup_manager_with_chat_plugins
        dispatcher = BaseDispatcher(
            plugin_manager=manager,
            plugin_type=ChatPlugin,
            dispatcher_name="Chat",
        )

        # All loaded plugins should be enabled
        for plugin in dispatcher._plugins:
            assert plugin.enabled is True
