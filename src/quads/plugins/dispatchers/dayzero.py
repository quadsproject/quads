import asyncio
import logging
import os
from typing import Dict, List, Optional
from quads.config import Config
from quads.plugins.dispatchers.base import MultiPluginDispatcher
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)

DAYZERO_LOG = "/var/log/quads-dayzero.log"


def _ensure_dayzero_log_handler():
    dayzero_logger = logging.getLogger("quads.plugins.dayzero")
    abs_log = os.path.abspath(DAYZERO_LOG)
    if any(
        isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == abs_log
        for h in dayzero_logger.handlers
    ):
        return
    try:
        handler = logging.FileHandler(DAYZERO_LOG)
        handler.setFormatter(logging.Formatter(Config.LOGFMT))
        dayzero_logger.addHandler(handler)
        dayzero_logger.setLevel(logging.DEBUG)
    except PermissionError:
        logger.warning(f"Cannot write to {DAYZERO_LOG}, dayzero logs will use standard logging only")


class DayzeroDispatcher(MultiPluginDispatcher[DayzeroPlugin]):

    def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
        super().__init__(plugin_manager, DayzeroPlugin, "Dayzero", plugin_names=plugin_names)
        _ensure_dayzero_log_handler()

    async def run_dayzero(
        self,
        host: str,
        cloud: str,
        schedule_data: dict,
    ) -> Dict[str, bool]:
        plugins = self.get_active_plugins()

        if not plugins:
            logger.debug("No dayzero plugins enabled")
            return {}

        tasks = []
        plugin_names = []

        for plugin in plugins:
            if not plugin.enabled:
                continue
            tasks.append(self._execute_plugin(plugin, host, cloud, schedule_data))
            plugin_names.append(plugin.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        dayzero_logger = logging.getLogger("quads.plugins.dayzero")
        for plugin_name, result in zip(plugin_names, results):
            if isinstance(result, Exception):
                dayzero_logger.error(f"dayzero plugin {plugin_name} raised exception: {result}")
                result_map[plugin_name] = False
            else:
                result_map[plugin_name] = result

        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"dayzero completed: {success_count}/{len(result_map)} plugins succeeded for {host}")

        return result_map

    async def _execute_plugin(
        self, plugin: DayzeroPlugin, host: str, cloud: str, schedule_data: dict
    ) -> bool:
        dayzero_logger = logging.getLogger("quads.plugins.dayzero")
        try:
            dayzero_logger.info(f"Running dayzero plugin {plugin.name} on {host}")
            success = await plugin.execute(host=host, cloud=cloud, schedule_data=schedule_data)
            if success:
                dayzero_logger.info(f"dayzero plugin {plugin.name} succeeded on {host}")
            else:
                dayzero_logger.warning(f"dayzero plugin {plugin.name} returned failure on {host}")
            return success
        except Exception as e:
            dayzero_logger.error(f"dayzero plugin {plugin.name} exception on {host}: {e}")
            return False


_dispatcher_instance: Optional[DayzeroDispatcher] = None


def get_dayzero_dispatcher(plugin_manager: Optional[PluginManager] = None) -> DayzeroDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize DayzeroDispatcher")
        _dispatcher_instance = DayzeroDispatcher(plugin_manager)

    return _dispatcher_instance
