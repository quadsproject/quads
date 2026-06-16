import logging
from typing import Optional
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.plugins.manager import PluginManager, get_plugin_manager

logger = logging.getLogger(__name__)


class SwitchDispatcher(SinglePluginDispatcher[SwitchPlugin]):
    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, SwitchPlugin, "Switch")

    async def configure(self, host: str, old_cloud: str, new_cloud: str) -> bool:
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        logger.info(f"Configuring switch for {host} from {old_cloud} to {new_cloud} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.configure(host, old_cloud, new_cloud)
        except Exception as e:
            logger.error(f"Failed to configure switch: {e}")
            return False

    async def modify(
        self,
        host: str,
        change: bool = False,
        overrides: Optional[dict] = None,
    ) -> bool:
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        logger.info(f"Modifying switch for {host} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.modify(host, change, overrides)
        except Exception as e:
            logger.error(f"Failed to modify switch: {e}")
            return False

    async def verify(self, host: str = None, cloud: str = None, change: bool = False) -> bool:
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        component = host if host else cloud
        logger.info(f"Verifying switch for {component} via {self._default_plugin.name}")
        try:
            await self._default_plugin.verify(host, cloud, change)
            return True
        except Exception as e:
            logger.error(f"Failed to verify switch: {e}")
            return False

    async def ls_config(self, cloud: str, all: bool = False) -> bool:
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False
        logger.info(f"Listing switch configuration for {cloud} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.ls_config(cloud, all)
        except Exception as e:
            logger.error(f"Failed to list switch configuration: {e}")
            return False


_dispatcher_instance: Optional[SwitchDispatcher] = None


def get_switch_dispatcher(plugin_manager: Optional[PluginManager] = None) -> SwitchDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            plugin_manager = get_plugin_manager()
        _dispatcher_instance = SwitchDispatcher(plugin_manager)

    return _dispatcher_instance


async def configure(host: str, old_cloud: str, new_cloud: str) -> bool:
    dispatcher = get_switch_dispatcher()
    return await dispatcher.configure(host, old_cloud, new_cloud)


async def modify(
    host: str,
    change: bool = False,
    overrides: Optional[dict] = None,
) -> bool:
    dispatcher = get_switch_dispatcher()
    return await dispatcher.modify(host, change, overrides)


async def verify(host: str = None, cloud: str = None, change: bool = False) -> bool:
    dispatcher = get_switch_dispatcher()
    return await dispatcher.verify(host, cloud, change)


async def ls_config(cloud: str, all: bool = False) -> bool:
    dispatcher = get_switch_dispatcher()
    return await dispatcher.ls_config(cloud, all)
