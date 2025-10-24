#!/usr/bin/env python3
"""
Notification Dispatcher - Orchestrates multiple notification plugins
"""
import asyncio
import logging
from typing import List, Optional, Dict
from quads.plugins.interfaces.notifier import NotifierPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    Dispatches notifications to all enabled notifier plugins.

    This provides a single interface for the core code to send notifications
    without knowing which specific notifiers are configured.
    """

    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager = plugin_manager
        self._notifiers: List[NotifierPlugin] = []
        self._refresh_notifiers()

    def _refresh_notifiers(self):
        """Refresh the list of enabled notifier plugins"""
        self._notifiers = self.plugin_manager.get_plugins_by_type(NotifierPlugin)
        if self._notifiers:
            logger.info(f"Loaded {len(self._notifiers)} notifier plugins: " f"{[n.name for n in self._notifiers]}")
        else:
            logger.warning("No notifier plugins are enabled")

    async def send_notification(
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> Dict[str, bool]:
        """
        Send notification via all enabled notifiers.

        Args:
            subject: Notification subject/title
            message: Notification body/content
            recipients: List of recipient identifiers (emails, slack channels, etc.)
            priority: Notification priority (low, normal, high, urgent)
            **kwargs: Additional plugin-specific parameters

        Returns:
            Dict mapping notifier name to success status
            Example: {"email_notifier": True, "slack_notifier": False}
        """
        if not self._notifiers:
            logger.warning("No notifiers available to send notification")
            return {}

        # Create tasks for all notifiers
        tasks = []
        notifier_names = []

        for notifier in self._notifiers:
            if not notifier.enabled:
                continue

            tasks.append(self._send_with_notifier(notifier, subject, message, recipients, priority, **kwargs))
            notifier_names.append(notifier.name)

        # Execute all notifiers in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build result map
        result_map = {}
        for notifier_name, result in zip(notifier_names, results):
            if isinstance(result, Exception):
                logger.error(f"Notifier {notifier_name} raised exception: {result}")
                result_map[notifier_name] = False
            else:
                result_map[notifier_name] = result

        # Log summary
        success_count = sum(1 for v in result_map.values() if v)
        logger.info(f"Notification sent via {success_count}/{len(result_map)} notifiers")

        return result_map

    async def _send_with_notifier(
        self, notifier: NotifierPlugin, subject: str, message: str, recipients: List[str], priority: str, **kwargs
    ) -> bool:
        """Send notification with a single notifier, handling errors gracefully"""
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
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> Dict[str, bool]:
        """
        Synchronous wrapper for send_notification.

        Use this from non-async code (e.g., existing QUADS tools).
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_notification(subject, message, recipients, priority, **kwargs))
        finally:
            loop.close()

    def get_enabled_notifiers(self) -> List[str]:
        """Get list of currently enabled notifier names"""
        return [n.name for n in self._notifiers if n.enabled]

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all notifiers"""
        results = {}
        for notifier in self._notifiers:
            try:
                results[notifier.name] = notifier.health_check()
            except Exception as e:
                logger.error(f"Health check failed for {notifier.name}: {e}")
                results[notifier.name] = False
        return results


# Singleton instance for easy access throughout codebase
_dispatcher_instance: Optional[NotificationDispatcher] = None


def get_notification_dispatcher(plugin_manager: Optional[PluginManager] = None) -> NotificationDispatcher:
    """
    Get the global NotificationDispatcher instance.

    Args:
        plugin_manager: PluginManager instance (required on first call)

    Returns:
        NotificationDispatcher singleton instance
    """
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize NotificationDispatcher")
        _dispatcher_instance = NotificationDispatcher(plugin_manager)

    return _dispatcher_instance


def notify(subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs) -> Dict[str, bool]:
    """
    Convenience function to send notifications from anywhere in the codebase.

    Example:
        from quads.plugins.notifier_dispatcher import notify

        notify(
            subject="Cloud Assignment Ending Soon",
            message="Your cloud 'cloud01' will expire in 3 days",
            recipients=["user@example.com"],
            priority="high"
        )
    """
    dispatcher = get_notification_dispatcher()
    return dispatcher.send_notification_sync(subject, message, recipients, priority, **kwargs)
