import logging
from typing import Dict, Optional, Type, List

from quads.plugins.base import BasePlugin
from quads.plugins.discovery import PluginDiscovery
from quads.config import Config

logger = logging.getLogger(__name__)

_manager_instance: Optional["PluginManager"] = None


class PluginManager:
    """Manages plugin lifecycle"""

    def __init__(self, config: Dict = None):
        self.config = config or Config
        self.discovery = PluginDiscovery()
        self.available_plugins: Dict[str, Type[BasePlugin]] = {}
        self.loaded_plugins: Dict[str, BasePlugin] = {}

    def initialize(self):
        """Discover and load configured plugins"""
        self.available_plugins = self.discovery.discover_plugins()

        # Load plugins from config
        plugin_config = self.config.get("plugins", {})
        for plugin_name, plugin_settings in plugin_config.items():
            if plugin_settings.get("enabled", False):
                self.load_plugin(plugin_name, plugin_settings)

    def load_plugin(self, name: str, config: Dict) -> Optional[BasePlugin]:
        """Load and initialize a specific plugin"""
        if name not in self.available_plugins:
            logger.error(f"Plugin {name} not found")
            return None

        try:
            plugin_class = self.available_plugins[name]
            plugin_instance = plugin_class(config)

            if plugin_instance.initialize(self):
                self.loaded_plugins[name] = plugin_instance
                logger.debug(f"Loaded plugin: {name} v{plugin_instance.version}")
                return plugin_instance
            else:
                logger.error(f"Plugin {name} failed to initialize")
                return None
        except Exception as e:
            logger.error(f"Error loading plugin {name}: {e}")
            return None

    def get_plugin(self, name: str, plugin_type: Type = BasePlugin) -> Optional[BasePlugin]:
        """Get a loaded plugin by name and type"""
        plugin = self.loaded_plugins.get(name)
        if plugin and isinstance(plugin, plugin_type):
            return plugin
        return None

    def get_plugins_by_type(self, plugin_type: Type) -> List[BasePlugin]:
        """Get all loaded plugins of a specific type"""
        return [p for p in self.loaded_plugins.values() if isinstance(p, plugin_type)]


def get_plugin_manager(config=None) -> "PluginManager":
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = PluginManager(config)
        _manager_instance.initialize()
    return _manager_instance


def reset_plugin_manager():
    global _manager_instance
    _manager_instance = None
