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

    def __init__(
        self,
        plugin_manager: PluginManager,
        plugin_type: Type[T],
        dispatcher_name: str,
        plugin_name: Optional[str] = None,
        plugin_names: Optional[List[str]] = None,
    ):
        """
        Args:
            plugin_manager: The PluginManager instance
            plugin_type: The plugin interface class (e.g., ProvisionerPlugin)
            dispatcher_name: Name for logging (e.g., "Provisioner")
            plugin_name: Optional specific plugin to use (for SinglePluginDispatcher)
            plugin_names: Optional list of plugins to use (for MultiPluginDispatcher)
        """
        self.plugin_manager = plugin_manager
        self.plugin_type = plugin_type
        self.dispatcher_name = dispatcher_name
        self._plugins: List[T] = []
        self._default_plugin: Optional[T] = None
        self._selected_plugin_name: Optional[str] = plugin_name
        self._selected_plugin_names: Optional[List[str]] = plugin_names
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

            # If a specific plugin was requested, validate and use it
            if self._selected_plugin_name:
                plugin = self.get_plugin_by_name(self._selected_plugin_name)
                if not plugin:
                    available = [p.name for p in self._plugins]
                    raise ValueError(
                        f"Plugin '{self._selected_plugin_name}' not found or not enabled. "
                        f"Available plugins: {available}"
                    )
                self._default_plugin = plugin
                logger.info(f"Using explicitly selected plugin: {self._selected_plugin_name}")

            # If specific plugin names were requested for filtering, validate them
            if self._selected_plugin_names:
                for name in self._selected_plugin_names:
                    if not self.get_plugin_by_name(name):
                        available = [p.name for p in self._plugins]
                        raise ValueError(
                            f"Plugin '{name}' not found or not enabled. " f"Available plugins: {available}"
                        )
                logger.info(f"Filtering to specific plugins: {self._selected_plugin_names}")
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

    def get_active_plugin(self) -> Optional[T]:
        """
        Get the active plugin for SinglePluginDispatcher.

        This is either the explicitly selected plugin (if specified at init)
        or the default plugin (first enabled).

        Returns:
            The active plugin to use for operations
        """
        return self._default_plugin

    def get_active_plugins(self) -> List[T]:
        """
        Get the active plugins for MultiPluginDispatcher.

        This is either the explicitly selected plugins (if specified at init)
        or all enabled plugins.

        Returns:
            List of plugins to use for operations
        """
        if self._selected_plugin_names:
            # Return only the filtered plugins
            filtered = []
            for name in self._selected_plugin_names:
                plugin = self.get_plugin_by_name(name)
                if plugin:
                    filtered.append(plugin)
            return filtered

        return self._plugins


class SinglePluginDispatcher(BaseDispatcher[T]):
    """
    Single Plugin Dispatcher - Routes calls to ONLY ONE plugin.

    Use this for operations that should only happen once:
    - Hardware management (don't reboot via multiple plugins!)
    - Provisioning (don't provision via multiple systems!)
    - Switch configuration (don't configure via multiple protocols!)
    - Host release/migration (don't move via multiple methods!)

    Plugin Selection:
    - By default, uses the first enabled plugin
    - Can specify plugin_name at initialization to use a specific plugin
    - Selection is persistent for the lifetime of the dispatcher instance

    Example:
        class HardwareDispatcher(SinglePluginDispatcher[HardwarePlugin]):
            def __init__(self, plugin_manager: PluginManager, plugin_name: Optional[str] = None):
                super().__init__(plugin_manager, HardwarePlugin, "Hardware", plugin_name=plugin_name)

            async def reboot_server(self, graceful: bool = True) -> bool:
                plugin = self.get_active_plugin()
                if not plugin:
                    logger.error("No hardware plugin enabled")
                    return False
                return await plugin.reboot_server(graceful)

        # Usage:
        # Use default plugin
        dispatcher = HardwareDispatcher(plugin_manager)
        await dispatcher.reboot_server()

        # Use specific plugin
        dispatcher = HardwareDispatcher(plugin_manager, plugin_name="ilo")
        await dispatcher.reboot_server()  # Always uses iLO
    """

    pass


class MultiPluginDispatcher(BaseDispatcher[T]):
    """
    Multi Plugin Dispatcher - Routes calls to ALL enabled plugins (or filtered subset).

    Use this for broadcast operations:
    - Notifications (send to email + Slack + Google Chat + etc.)
    - Ticketing (create tickets in multiple systems if needed)
    - Logging/Audit (send to multiple audit systems)

    Plugin Filtering:
    - By default, uses ALL enabled plugins
    - Can specify plugin_names at initialization to filter to specific plugins
    - Filtering is persistent for the lifetime of the dispatcher instance

    Example:
        class NotificationDispatcher(MultiPluginDispatcher[NotifierPlugin]):
            def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
                super().__init__(plugin_manager, NotifierPlugin, "Notification", plugin_names=plugin_names)

            async def send_notification(self, subject: str, message: str, **kwargs) -> Dict[str, bool]:
                results = {}
                plugins = self.get_active_plugins()
                for plugin in plugins:
                    try:
                        await plugin.send_notification(subject, message, **kwargs)
                        results[plugin.name] = True
                    except Exception as e:
                        logger.error(f"Failed to notify via {plugin.name}: {e}")
                        results[plugin.name] = False
                return results

        # Usage:
        # Use all enabled plugins
        dispatcher = NotificationDispatcher(plugin_manager)
        await dispatcher.send_notification("Subject", "Message")

        # Use only Slack
        dispatcher = NotificationDispatcher(plugin_manager, plugin_names=["slack"])
        await dispatcher.send_notification("Subject", "Message")  # Only Slack
    """

    pass
