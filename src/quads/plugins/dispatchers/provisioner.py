import logging
from typing import List, Optional, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ProvisionerDispatcher(SinglePluginDispatcher[ProvisionerPlugin]):

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, ProvisionerPlugin, "Provisioner")

    async def prepare_host_provisioning(self, host_name: str, cloud: str, os_type: str) -> bool:
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return False

        logger.info(f"Preparing host provisioning for {host_name} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.prepare_host_provisioning(host_name, cloud, os_type)
        except Exception as e:
            logger.error(f"Preparing host provisioning failed: {e}")
            return False

    async def get_all_hosts(self) -> List[str]:
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return []

        try:
            return await self._default_plugin.get_all_hosts()
        except Exception as e:
            logger.error(f"Failed to get all hosts: {e}")
            return []

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


async def prepare_host_provisioning(hostname: str, build: bool = True) -> bool:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.prepare_host_provisioning(hostname, build)


async def get_all_hosts() -> List[str]:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_all_hosts()


async def get_host_param(hostname: str, param: str) -> Optional[Any]:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_host_param(hostname, param)


async def set_host_param(hostname: str, param: str, value: Any) -> bool:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.set_host_param(hostname, param, value)
