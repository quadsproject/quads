#!/usr/bin/env python3
"""
Provisioner Dispatcher - Automatically routes to enabled provisioning backend
"""
import logging
from typing import Optional, Any
from quads.plugins.dispatchers.base import BaseDispatcher
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ProvisionerDispatcher(BaseDispatcher[ProvisionerPlugin]):
    """
    Dispatches provisioning operations to the enabled provisioner plugin.

    Core code calls generic methods like provision_host() without knowing
    if it's using Foreman, Ansible AWX, Cobbler, etc.
    """

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, ProvisionerPlugin, "Provisioner")

    async def provision_host(self, hostname: str, build: bool = True) -> bool:
        """
        Provision a host using the enabled provisioner backend.

        Core code doesn't need to know if this is Foreman, AWX, etc.
        """
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return False

        logger.info(f"Provisioning {hostname} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.provision_host(hostname, build)
        except Exception as e:
            logger.error(f"Provisioning failed: {e}")
            return False

    async def get_host_param(self, hostname: str, param: str) -> Optional[Any]:
        """Get host parameter from provisioner backend"""
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return None

        try:
            return await self._default_plugin.get_host_param(hostname, param)
        except Exception as e:
            logger.error(f"Failed to get host param: {e}")
            return None

    async def set_host_param(self, hostname: str, param: str, value: Any) -> bool:
        """Set host parameter in provisioner backend"""
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return False

        try:
            return await self._default_plugin.set_host_param(hostname, param, value)
        except Exception as e:
            logger.error(f"Failed to set host param: {e}")
            return False


# Singleton instance
_dispatcher_instance: Optional[ProvisionerDispatcher] = None


def get_provisioner_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ProvisionerDispatcher:
    """Get the global ProvisionerDispatcher instance"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ProvisionerDispatcher")
        _dispatcher_instance = ProvisionerDispatcher(plugin_manager)

    return _dispatcher_instance


# Convenience functions for core code
async def provision_host(hostname: str, build: bool = True) -> bool:
    """
    Convenience function to provision a host.

    Example:
        from quads.plugins.provisioner_dispatcher import provision_host

        # Core code doesn't know/care if this is Foreman, AWX, etc.
        success = await provision_host("host01.example.com")
    """
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.provision_host(hostname, build)


async def get_host_param(hostname: str, param: str) -> Optional[Any]:
    """Get host parameter from provisioner"""
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_host_param(hostname, param)


async def set_host_param(hostname: str, param: str, value: Any) -> bool:
    """Set host parameter in provisioner"""
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.set_host_param(hostname, param, value)
