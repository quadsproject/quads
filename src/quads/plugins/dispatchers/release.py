import logging
import asyncio
from typing import Optional, Dict, Any
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.release import ReleasePlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ReleaseDispatcher(SinglePluginDispatcher[ReleasePlugin]):

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, ReleasePlugin, "Release")

    async def move_and_rebuild(
        self, host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False
    ) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        logger.info(f"Moving {host} to {new_cloud} (rebuild={rebuild}) via {self._default_plugin.name}")
        try:
            return await self._default_plugin.move_and_rebuild(host, new_cloud, semaphore, rebuild)
        except Exception as e:
            logger.error(f"Failed to move/rebuild host: {e}")
            return False

    async def prepare_host_hardware(
        self, host: str, rack: str, uloc: str, blade: str, boot_order: str, interfaces_path: str
    ) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        try:
            return await self._default_plugin.prepare_host_hardware(
                host, rack, uloc, blade, boot_order, interfaces_path
            )
        except Exception as e:
            logger.error(f"Failed to prepare host hardware: {e}")
            return False

    async def prepare_host_provisioning(
        self, host: str, cloud: str, os_type: str, semaphore: asyncio.Semaphore
    ) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        try:
            return await self._default_plugin.prepare_host_provisioning(host, cloud, os_type, semaphore)
        except Exception as e:
            logger.error(f"Failed to prepare host provisioning: {e}")
            return False

    async def power_on_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        try:
            return await self._default_plugin.power_on_host(host, rack, uloc, blade)
        except Exception as e:
            logger.error(f"Failed to power on host: {e}")
            return False

    async def power_off_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        try:
            return await self._default_plugin.power_off_host(host, rack, uloc, blade)
        except Exception as e:
            logger.error(f"Failed to power off host: {e}")
            return False

    async def cleanup_virtual_media(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return False

        try:
            return await self._default_plugin.cleanup_virtual_media(host, rack, uloc, blade)
        except Exception as e:
            logger.error(f"Failed to cleanup virtual media: {e}")
            return False

    def get_release_info(self) -> Optional[Dict[str, Any]]:
        if not self._default_plugin:
            logger.error("No release plugin enabled")
            return None

        try:
            return self._default_plugin.get_release_info()
        except Exception as e:
            logger.error(f"Failed to get release info: {e}")
            return None


_dispatcher_instance: Optional[ReleaseDispatcher] = None


def get_release_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ReleaseDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ReleaseDispatcher")
        _dispatcher_instance = ReleaseDispatcher(plugin_manager)

    return _dispatcher_instance


async def move_and_rebuild(host: str, new_cloud: str, semaphore: asyncio.Semaphore, rebuild: bool = False) -> bool:
    dispatcher = get_release_dispatcher()
    return await dispatcher.move_and_rebuild(host, new_cloud, semaphore, rebuild)


async def power_on_host(host: str, rack: str, uloc: str, blade: str) -> bool:
    dispatcher = get_release_dispatcher()
    return await dispatcher.power_on_host(host, rack, uloc, blade)


async def power_off_host(host: str, rack: str, uloc: str, blade: str) -> bool:
    dispatcher = get_release_dispatcher()
    return await dispatcher.power_off_host(host, rack, uloc, blade)
