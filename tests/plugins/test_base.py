"""Tests for base plugin functionality"""

import logging

from quads.plugins.base import BasePlugin


class TestBasePlugin:
    """Test cases for BasePlugin class"""

    def test_plugin_initialization_with_config(self):
        """Test that plugin initializes with provided config"""
        config = {"enabled": True, "test_param": "value"}
        plugin = BasePlugin(config)
        assert plugin.config == config
        assert plugin._enabled is True

    def test_plugin_initialization_default_enabled(self):
        """Test that plugin is enabled by default when not specified"""
        config = {}
        plugin = BasePlugin(config)
        assert plugin.enabled is True

    def test_plugin_initialization_disabled(self):
        """Test that plugin can be disabled via config"""
        config = {"enabled": False}
        plugin = BasePlugin(config)
        assert plugin.enabled is False

    def test_plugin_has_logger(self):
        """Test that plugin initializes with a logger"""
        config = {"enabled": True}

        class TestPlugin(BasePlugin):
            name = "test_plugin"

        plugin = TestPlugin(config)
        assert plugin.logger is not None
        assert isinstance(plugin.logger, logging.Logger)
        assert "quads.plugins.test_plugin" in plugin.logger.name

    def test_plugin_metadata_defaults(self):
        """Test that plugin has default metadata attributes"""
        config = {}
        plugin = BasePlugin(config)
        assert plugin.name == ""
        assert plugin.version == "1.0.0"
        assert plugin.description == ""
        assert plugin.author == ""

    def test_plugin_metadata_custom(self):
        """Test that plugin can have custom metadata"""

        class CustomPlugin(BasePlugin):
            name = "custom"
            version = "2.0.0"
            description = "Custom plugin"
            author = "Test Author"

        config = {}
        plugin = CustomPlugin(config)
        assert plugin.name == "custom"
        assert plugin.version == "2.0.0"
        assert plugin.description == "Custom plugin"
        assert plugin.author == "Test Author"

    def test_enabled_property(self):
        """Test the enabled property returns correct value"""
        config_enabled = {"enabled": True}
        config_disabled = {"enabled": False}

        plugin_enabled = BasePlugin(config_enabled)
        plugin_disabled = BasePlugin(config_disabled)

        assert plugin_enabled.enabled is True
        assert plugin_disabled.enabled is False

    def test_plugin_config_access(self):
        """Test that plugin can access config values"""
        config = {
            "enabled": True,
            "url": "https://example.com",
            "timeout": 30,
            "nested": {"key": "value"},
        }
        plugin = BasePlugin(config)
        assert plugin.config.get("url") == "https://example.com"
        assert plugin.config.get("timeout") == 30
        assert plugin.config.get("nested") == {"key": "value"}

    def test_plugin_config_missing_key(self):
        """Test that plugin returns None for missing config keys"""
        config = {"enabled": True}
        plugin = BasePlugin(config)
        assert plugin.config.get("missing_key") is None
        assert plugin.config.get("missing_key", "default") == "default"
