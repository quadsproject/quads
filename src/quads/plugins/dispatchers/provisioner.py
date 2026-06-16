import logging
from typing import List, Optional
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.plugins.manager import PluginManager, get_plugin_manager

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

    async def get_host(self, hostname: str) -> dict:
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return {}

        try:
            return await self._default_plugin.get_host(hostname)
        except Exception as e:
            logger.error(f"Failed to get host: {e}")
            return {}

    async def get_images(self) -> List[str]:
        if not self._default_plugin:
            logger.error("No provisioner plugin enabled")
            return []

        try:
            return await self._default_plugin.get_images()
        except Exception as e:
            logger.error(f"Failed to get images: {e}")
            return []


_dispatcher_instance: Optional[ProvisionerDispatcher] = None


def get_provisioner_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ProvisionerDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            plugin_manager = get_plugin_manager()
        _dispatcher_instance = ProvisionerDispatcher(plugin_manager)

    return _dispatcher_instance


async def prepare_host_provisioning(hostname: str, build: bool = True) -> bool:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.prepare_host_provisioning(hostname, build)


async def get_all_hosts() -> List[str]:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_all_hosts()


async def get_host(hostname: str) -> dict:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_host(hostname)


async def get_images() -> List[str]:
    dispatcher = get_provisioner_dispatcher()
    return await dispatcher.get_images()
