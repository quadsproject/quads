#!/usr/bin/env python3
"""
Base Dispatcher Patterns - Two types of dispatchers for different use cases

1. SinglePluginDispatcher: Calls ONLY the default (first enabled) plugin
   Use for: Hardware, Provisioner, Switch, Release (operations that should only happen once)

2. MultiPluginDispatcher: Calls ALL enabled plugins
   Use for: Notifiers, Ticketing (broadcast operations to multiple providers)
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
    Base dispatcher - Common functionality for both dispatcher types.

    DO NOT USE THIS DIRECTLY - Use SinglePluginDispatcher or MultiPluginDispatcher instead.
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


class SinglePluginDispatcher(BaseDispatcher[T]):
    """
    Single Plugin Dispatcher - Routes calls to ONLY ONE plugin (the default).

    Use this for operations that should only happen once:
    - Hardware management (don't reboot via multiple plugins!)
    - Provisioning (don't provision via multiple systems!)
    - Switch configuration (don't configure via multiple protocols!)
    - Host release/migration (don't move via multiple methods!)

    Example:
        class HardwareDispatcher(SinglePluginDispatcher[HardwarePlugin]):
            def __init__(self, plugin_manager: PluginManager):
                super().__init__(plugin_manager, HardwarePlugin, "Hardware")

            async def reboot_server(self, graceful: bool = True) -> bool:
                if not self._default_plugin:
                    logger.error("No hardware plugin enabled")
                    return False
                return await self._default_plugin.reboot_server(graceful)
    """

    pass


class MultiPluginDispatcher(BaseDispatcher[T]):
    """
    Multi Plugin Dispatcher - Routes calls to ALL enabled plugins.

    Use this for broadcast operations:
    - Notifications (send to email + Slack + Google Chat + etc.)
    - Ticketing (create tickets in multiple systems if needed)
    - Logging/Audit (send to multiple audit systems)

    Example:
        class NotificationDispatcher(MultiPluginDispatcher[NotifierPlugin]):
            def __init__(self, plugin_manager: PluginManager):
                super().__init__(plugin_manager, NotifierPlugin, "Notification")

            def notify(self, subject: str, message: str, **kwargs) -> Dict[str, bool]:
                results = {}
                for plugin in self._plugins:
                    try:
                        plugin.send_notification(subject, message, **kwargs)
                        results[plugin.name] = True
                    except Exception as e:
                        logger.error(f"Failed to notify via {plugin.name}: {e}")
                        results[plugin.name] = False
                return results
    """

    pass
