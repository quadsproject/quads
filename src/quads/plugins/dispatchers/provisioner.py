import logging
from typing import Optional, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ProvisionerDispatcher(SinglePluginDispatcher[ProvisionerPlugin]):

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, ProvisionerPlugin, "Provisioner")

    async def provision_host(self, hostname: str, build: bool = True) -> bool:
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
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return None

        try:
            return await self._default_plugin.get_host_param(hostname, param)
        except Exception as e:
            logger.error(f"Failed to get host param: {e}")
            return None

    async def set_host_param(self, hostname: str, param: str, value: Any) -> bool:
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return False

        try:
            return await self._default_plugin.set_host_param(hostname, param, value)
        except Exception as e:
            logger.error(f"Failed to set host param: {e}")
            return False


_dispatcher_instance: Optional[ProvisionerDispatcher] = None


def get_provisioner_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ProvisionerDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ProvisionerDispatcher")
        _dispatcher_instance = ProvisionerDispatcher(plugin_manager)

    return _dispatcher_instance


async def provision_host(hostname: str, build: bool = True) -> bool:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.provision_host(hostname, build)


async def get_host_param(hostname: str, param: str) -> Optional[Any]:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_host_param(hostname, param)


async def set_host_param(hostname: str, param: str, value: Any) -> bool:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.set_host_param(hostname, param, value)
