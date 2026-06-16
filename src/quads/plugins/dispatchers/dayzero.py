import logging
import os
from typing import List, Optional, Union
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

    async def execute(self, host: Union[str, List[str]], cloud: str):
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No dayzero plugin enabled")
            return False

        try:
            logger.info(f"Executing dayzero via {plugin.name}")
            return await plugin.execute(host, cloud)
        except Exception as e:
            logger.error(f"Failed to execute dayzero script: {e}", exc_info=True)
            return False


_dispatcher_instance: Optional[DayzeroDispatcher] = None


def get_dayzero_dispatcher(plugin_manager: Optional[PluginManager] = None) -> DayzeroDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize DayzeroDispatcher")
        _dispatcher_instance = DayzeroDispatcher(plugin_manager)

    return _dispatcher_instance


async def execute(host, cloud):
    dispatcher = get_dayzero_dispatcher()
    return await dispatcher.execute(host, cloud)
