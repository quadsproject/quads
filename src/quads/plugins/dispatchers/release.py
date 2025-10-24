import logging
import asyncio
from typing import Optional
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
