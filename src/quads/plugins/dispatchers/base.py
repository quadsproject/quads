#!/usr/bin/env python3
"""
Base Dispatcher Pattern - Generic dispatcher for any plugin type
"""
import logging
from typing import List, Optional, Type, TypeVar, Generic
from quads.plugins.base import BasePlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)

# Generic type for plugin classes
T = TypeVar("T", bound=BasePlugin)


class BaseDispatcher(Generic[T]):
    """
    Base dispatcher that automatically discovers and routes to enabled plugins.

    This provides a generic interface so core code never needs to know
    which specific plugins are enabled - it just calls the dispatcher.
    """

    def __init__(self, plugin_manager: PluginManager, plugin_type: Type[T], dispatcher_name: str):
        """
        Args:
            plugin_manager: The PluginManager instance
            plugin_type: The plugin interface class (e.g., ProvisionerPlugin)
            dispatcher_name: Name for logging (e.g., "Provisioner")
        """
        self.plugin_manager = plugin_manager
        self.plugin_type = plugin_type
        self.dispatcher_name = dispatcher_name
        self._plugins: List[T] = []
        self._default_plugin: Optional[T] = None
        self._refresh_plugins()

    def _refresh_plugins(self):
        """Refresh the list of enabled plugins of this type"""
        self._plugins = self.plugin_manager.get_plugins_by_type(self.plugin_type)

        if self._plugins:
            logger.info(
                f"{self.dispatcher_name} dispatcher loaded {len(self._plugins)} plugins: "
                f"{[p.name for p in self._plugins]}"
            )
            # First enabled plugin becomes default
            self._default_plugin = self._plugins[0]
        else:
            logger.warning(f"No {self.dispatcher_name} plugins are enabled")
            self._default_plugin = None

    def get_default_plugin(self) -> Optional[T]:
        """Get the default plugin (first enabled plugin of this type)"""
        return self._default_plugin

    def get_plugin_by_name(self, name: str) -> Optional[T]:
        """Get a specific plugin by name"""
        for plugin in self._plugins:
            if plugin.name == name:
                return plugin
        return None

    def get_all_plugins(self) -> List[T]:
        """Get all enabled plugins of this type"""
        return self._plugins.copy()

    def has_plugins(self) -> bool:
        """Check if any plugins are enabled"""
        return len(self._plugins) > 0

    def get_enabled_plugin_names(self) -> List[str]:
        """Get names of all enabled plugins"""
        return [p.name for p in self._plugins if p.enabled]
