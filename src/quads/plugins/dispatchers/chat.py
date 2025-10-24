import asyncio
import logging
from typing import List, Optional, Dict
from quads.plugins.dispatchers.base import MultiPluginDispatcher
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class ChatDispatcher(MultiPluginDispatcher[ChatPlugin]):

    def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
        super().__init__(plugin_manager, ChatPlugin, "Chat", plugin_names=plugin_names)

    async def send_message(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, bool]:

        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning("No notifiers available to send notification")
            return {}

        tasks = []
        plugin_names = []

        for plugin in plugins:
            if not plugin.enabled:
                continue

            tasks.append(self._send_with_plugin(plugin, message, channels, **kwargs))
            plugin_names.append(plugin.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        for plugin_name, result in zip(plugin_names, results):
            if isinstance(result, Exception):
                logger.error(f"Chat plugin {plugin_name} raised exception: {result}")
                result_map[plugin_name] = False
            else:
                result_map[plugin_name] = result

        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"Notification sent via {success_count}/{len(result_map)} chat plugins")

        return result_map

    async def _send_with_plugin(
        self, plugin: ChatPlugin, message: str, channels: Optional[List[str]] = None, **kwargs
    ) -> bool:
        try:
            logger.debug(f"Sending chat message via {plugin.name}")
            success = await plugin.send_message(message=message, channels=channels, **kwargs)

            if success:
                logger.info(f"✓ Chat message sent successfully via {plugin.name}")
            else:
                logger.warning(f"✗ Chat message failed via {plugin.name}")

            return success

        except Exception as e:
            logger.error(f"Exception in chat plugin {plugin.name}: {e}", exc_info=True)
            return False

    def send_message_sync(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> Dict[str, bool]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_message(message, channels, **kwargs))
        finally:
            loop.close()

    def get_enabled_plugins(self) -> List[str]:
        return [p.name for p in self._plugins if p.enabled]


_dispatcher_instance: Optional[ChatDispatcher] = None


def get_chat_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ChatDispatcher:

    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize ChatDispatcher")
        _dispatcher_instance = ChatDispatcher(plugin_manager)

    return _dispatcher_instance


def send_message(
    message: str,
    channels: Optional[List[str]] = None,
    **kwargs,
) -> Dict[str, bool]:

    dispatcher = get_chat_dispatcher()
    return dispatcher.send_message_sync(message, channels, **kwargs)
