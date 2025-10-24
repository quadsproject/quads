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

    async def send_notification(
        self,
        subject: str,
        message: str,
        recipients: List[str],
        priority: str = "normal",
        **kwargs,
    ) -> Dict[str, bool]:

        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning("No notifiers available to send notification")
            return {}

        tasks = []
        notifier_names = []

        for notifier in plugins:
            if not notifier.enabled:
                continue

            tasks.append(self._send_with_notifier(notifier, subject, message, recipients, priority, **kwargs))
            notifier_names.append(notifier.name)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        result_map = {}
        for notifier_name, result in zip(notifier_names, results):
            if isinstance(result, Exception):
                logger.error(f"Notifier {notifier_name} raised exception: {result}")
                result_map[notifier_name] = False
            else:
                result_map[notifier_name] = result

        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"Notification sent via {success_count}/{len(result_map)} notifiers")

        return result_map

    async def _send_with_notifier(
        self, notifier: ChatPlugin, subject: str, message: str, recipients: List[str], priority: str, **kwargs
    ) -> bool:
        try:
            logger.debug(f"Sending notification via {notifier.name}")
            success = await notifier.send_notification(
                subject=subject, message=message, recipients=recipients, priority=priority, **kwargs
            )

            if success:
                logger.info(f"✓ Notification sent successfully via {notifier.name}")
            else:
                logger.warning(f"✗ Notification failed via {notifier.name}")

            return success

        except Exception as e:
            logger.error(f"Exception in notifier {notifier.name}: {e}", exc_info=True)
            return False

    def send_notification_sync(
        self,
        subject: str,
        message: str,
        recipients: List[str],
        priority: str = "normal",
        **kwargs,
    ) -> Dict[str, bool]:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_notification(subject, message, recipients, priority, **kwargs))
        finally:
            loop.close()

    def get_enabled_notifiers(self) -> List[str]:
        return [n.name for n in self._plugins if n.enabled]

    async def health_check_all(self) -> Dict[str, bool]:
        results = {}
        for notifier in self._plugins:
            try:
                results[notifier.name] = notifier.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {notifier.name}: {e}")
                results[notifier.name] = False
        return results


_dispatcher_instance: Optional[ChatDispatcher] = None


def get_chat_dispatcher(plugin_manager: Optional[PluginManager] = None) -> ChatDispatcher:

    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize NotificationDispatcher")
        _dispatcher_instance = ChatDispatcher(plugin_manager)

    return _dispatcher_instance


def notify(
    subject: str,
    message: str,
    recipients: List[str],
    priority: str = "normal",
    **kwargs,
) -> Dict[str, bool]:

    dispatcher = get_chat_dispatcher()
    return dispatcher.send_notification_sync(subject, message, recipients, priority, **kwargs)
