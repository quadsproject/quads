#!/usr/bin/env python3
"""
Base Dispatcher Patterns - Two types of dispatchers for different use cases

1. SinglePluginDispatcher: Calls ONLY the default (first enabled) plugin
   Use for: Hardware, Provisioner, Switch, Release (operations that should only happen once)

2. MultiPluginDispatcher: Calls ALL enabled plugins
   Use for: Notifiers, Ticketing (broadcast operations to multiple providers)
"""

import asyncio
import logging
from typing import List, Optional, Type, TypeVar, Generic, Callable, Any, Dict, Awaitable
from quads.plugins.base import BasePlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)

# Generic type for plugin classes
T = TypeVar("T", bound=BasePlugin)


class BaseDispatcher(Generic[T]):

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
        self._default_plugin_class: Optional[Type[T]] = None
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
            # Store the plugin class as well
            self._default_plugin_class = type(self._default_plugin)

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
                self._default_plugin_class = type(plugin)
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
            self._default_plugin_class = None

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
        if self._selected_plugin_names:
            # Return only the filtered plugins
            filtered = []
            for name in self._selected_plugin_names:
                plugin = self.get_plugin_by_name(name)
                if plugin:
                    filtered.append(plugin)
            return filtered

        return self._plugins

    def _get_plugin_class(self) -> Optional[Type[T]]:
        return self._default_plugin_class


class SinglePluginDispatcher(BaseDispatcher[T]):

    async def dispatch_single(
        self,
        operation_name: str,
        plugin_callable: Callable[[T], Awaitable[Any]],
        default_return: Any = None,
        log_operation: bool = True,
    ) -> Any:
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error(f"No {self.dispatcher_name} plugin enabled for {operation_name}")
            return default_return

        if log_operation:
            logger.info(f"{operation_name} via {plugin.name}")

        try:
            return await plugin_callable(plugin)
        except Exception as e:
            logger.error(f"Failed to {operation_name} via {plugin.name}: {e}", exc_info=True)
            return default_return

    def dispatch_single_sync(
        self,
        operation_name: str,
        plugin_callable: Callable[[T], Any],
        default_return: Any = None,
        log_operation: bool = True,
    ) -> Any:
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error(f"No {self.dispatcher_name} plugin enabled for {operation_name}")
            return default_return

        if log_operation:
            logger.info(f"{operation_name} via {plugin.name}")

        try:
            return plugin_callable(plugin)
        except Exception as e:
            logger.error(f"Failed to {operation_name} via {plugin.name}: {e}", exc_info=True)
            return default_return


class MultiPluginDispatcher(BaseDispatcher[T]):
    async def dispatch_all(
        self,
        operation_name: str,
        plugin_callable: Callable[[T], Awaitable[Any]],
        skip_disabled: bool = True,
        log_summary: bool = True,
    ) -> Dict[str, Any]:
        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning(f"No {self.dispatcher_name} plugins available for {operation_name}")
            return {}

        tasks = []
        plugin_names = []

        for plugin in plugins:
            if skip_disabled and not plugin.enabled:
                continue

            tasks.append(self._execute_plugin_call(plugin, plugin_callable, operation_name))
            plugin_names.append(plugin.name)

        if not tasks:
            logger.warning(f"No enabled {self.dispatcher_name} plugins for {operation_name}")
            return {}

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        for plugin_name, result in zip(plugin_names, results):
            if isinstance(result, Exception):
                logger.error(f"{self.dispatcher_name} plugin {plugin_name} raised exception: {result}")
                result_map[plugin_name] = False
            else:
                result_map[plugin_name] = result

        if log_summary:
            success_count = sum(1 for v in result_map.values() if v)
            logger.info(f"{operation_name} completed: {success_count}/{len(result_map)} plugins succeeded")

        return result_map

    async def _execute_plugin_call(
        self, plugin: T, plugin_callable: Callable[[T], Awaitable[Any]], operation_name: str
    ) -> Any:
        try:
            logger.debug(f"Executing {operation_name} via {plugin.name}")
            result = await plugin_callable(plugin)

            if result:
                logger.info(f"✓ {operation_name} succeeded via {plugin.name}")
            else:
                logger.warning(f"✗ {operation_name} failed via {plugin.name}")

            return result

        except Exception as e:
            logger.error(f"Exception in {self.dispatcher_name} plugin {plugin.name}: {e}", exc_info=True)
            raise

    def dispatch_all_sync(
        self,
        operation_name: str,
        plugin_callable: Callable[[T], Awaitable[Any]],
        skip_disabled: bool = True,
        log_summary: bool = True,
    ) -> Dict[str, Any]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                self.dispatch_all(operation_name, plugin_callable, skip_disabled, log_summary)
            )
        finally:
            loop.close()

    def get_enabled_plugin_names_list(self) -> List[str]:
        """
        Get list of enabled plugin names.

        Returns:
            List of names of enabled plugins
        """
        return [p.name for p in self._plugins if p.enabled]

    async def health_check_all(self) -> Dict[str, bool]:
        """
        Run health checks on all plugins.

        Returns:
            Dict mapping plugin names to health check results (True/False)
        """
        results = {}
        for plugin in self._plugins:
            try:
                if hasattr(plugin, "health_check"):
                    results[plugin.name] = plugin.health_check()
                else:
                    results[plugin.name] = True
            except Exception as e:
                logger.error(f"Health check failed for {plugin.name}: {e}")
                results[plugin.name] = False
        return results
