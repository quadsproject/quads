import logging
import os
from typing import List, Optional
from quads.config import Config
from quads.plugins.dispatchers.base import MultiPluginDispatcher
from quads.plugins.interfaces.dayzero import DayzeroPlugin
from quads.plugins.manager import PluginManager, get_plugin_manager

logger = logging.getLogger(__name__)

DAYZERO_LOG = "/var/log/quads-dayzero.log"


def _ensure_dayzero_log_handler():
    abs_log = os.path.abspath(DAYZERO_LOG)
    try:
        handler = logging.FileHandler(DAYZERO_LOG)
        handler.setFormatter(logging.Formatter(Config.LOGFMT))
    except OSError:
        logger.warning(f"Cannot write to {DAYZERO_LOG}, dayzero logs will use standard logging only")
        return

    for logger_name in [__name__, "quads.plugins.builtin.dayzero.cloudcmd", "quads.plugins.builtin.dayzero.clouddata"]:
        target = logging.getLogger(logger_name)
        if not any(
            isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", None) == abs_log for h in target.handlers
        ):
            target.addHandler(handler)
            target.setLevel(logging.DEBUG)


class DayzeroDispatcher(MultiPluginDispatcher[DayzeroPlugin]):

    def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
        super().__init__(plugin_manager, DayzeroPlugin, "Dayzero", plugin_names=plugin_names)
        _ensure_dayzero_log_handler()

    async def execute(self, cloud: str):
        plugins = self.get_active_plugins()
        if not plugins:
            logger.error("No dayzero plugins enabled")
            return False

        results = await self.dispatch_all(
            f"dayzero for {cloud}",
            lambda plugin: plugin.execute(cloud),
        )
        return all(results.values()) if results else False


_dispatcher_instance: Optional[DayzeroDispatcher] = None


def get_dayzero_dispatcher(plugin_manager: Optional[PluginManager] = None) -> DayzeroDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            plugin_manager = get_plugin_manager()
        _dispatcher_instance = DayzeroDispatcher(plugin_manager)

    return _dispatcher_instance


async def execute(cloud):
    dispatcher = get_dayzero_dispatcher()
    return await dispatcher.execute(cloud)
