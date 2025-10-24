#!/usr/bin/env python3
"""
Notification Dispatcher - Orchestrates multiple notification plugins

Uses MultiPluginDispatcher because notifications should be sent to ALL
enabled channels (email + Slack + Google Chat + etc.) simultaneously.
"""
import asyncio
import logging
from typing import List, Optional, Dict
from quads.plugins.dispatchers.base import MultiPluginDispatcher
from quads.plugins.interfaces.notifier import NotifierPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class NotificationDispatcher(MultiPluginDispatcher[NotifierPlugin]):
    """
    Dispatches notifications to all enabled notifier plugins.

    This provides a single interface for the core code to send notifications
    without knowing which specific notifiers are configured.

    This is a MultiPluginDispatcher - notifications are sent to ALL enabled plugins
    (or filtered subset if plugin_names specified).

    Plugin Filtering:
    - By default, sends to ALL enabled notification plugins
    - Can specify plugin_names at initialization to filter to specific channels
    - Useful for priority-based routing, testing, or cost control

    Example:
        # Send to all enabled notifiers
        dispatcher = NotificationDispatcher(plugin_manager)

        # Send only to Slack (for urgent alerts)
        dispatcher = NotificationDispatcher(plugin_manager, plugin_names=["slack"])

        # Send to email and Google Chat
        dispatcher = NotificationDispatcher(plugin_manager, plugin_names=["email", "google_chat"])
    """

    def __init__(self, plugin_manager: PluginManager, plugin_names: Optional[List[str]] = None):
        super().__init__(plugin_manager, NotifierPlugin, "Notification", plugin_names=plugin_names)

    async def send_notification(
        self,
        subject: str,
        message: str,
        recipients: List[str],
        priority: str = "normal",
        **kwargs,
    ) -> Dict[str, bool]:
        """
        Send notification via active notifier plugins.

        Sends to ALL enabled plugins by default, or only to the filtered
        plugins if plugin_names was specified at dispatcher initialization.

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
        # Get active plugins (all or filtered based on initialization)
        plugins = self.get_active_plugins()

        if not plugins:
            logger.warning("No notifiers available to send notification")
            return {}

        # Create tasks for active notifiers
        tasks = []
        notifier_names = []

        for notifier in plugins:
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
        self,
        subject: str,
        message: str,
        recipients: List[str],
        priority: str = "normal",
        **kwargs,
    ) -> Dict[str, bool]:
        """
        Synchronous wrapper for send_notification.

        Use this from non-async code (e.g., existing QUADS tools).

        Args:
            subject: Notification subject/title
            message: Notification body/content
            recipients: List of recipient identifiers
            priority: Notification priority
            **kwargs: Additional plugin-specific parameters
        """
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.send_notification(subject, message, recipients, priority, **kwargs))
        finally:
            loop.close()

    def get_enabled_notifiers(self) -> List[str]:
        """Get list of currently enabled notifier names"""
        return [n.name for n in self._plugins if n.enabled]

    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all notifiers"""
        results = {}
        for notifier in self._plugins:
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
    Get the global NotificationDispatcher instance (sends to all enabled plugins).

    This singleton always sends to ALL enabled notification plugins.
    To send to specific plugins only, create a dispatcher instance directly:

        dispatcher = NotificationDispatcher(plugin_manager, plugin_names=["slack"])

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


def notify(
    subject: str,
    message: str,
    recipients: List[str],
    priority: str = "normal",
    **kwargs,
) -> Dict[str, bool]:
    """
    Convenience function to send notifications from anywhere in the codebase.

    Uses the global NotificationDispatcher instance which sends to all
    enabled notifiers by default.

    Args:
        subject: Notification subject/title
        message: Notification body/content
        recipients: List of recipient identifiers
        priority: Notification priority (low, normal, high, urgent)
        **kwargs: Additional plugin-specific parameters

    Example:
        from quads.plugins.dispatchers.notifier import notify

        # Send to all enabled notifiers
        notify(
            subject="Cloud Assignment Ending Soon",
            message="Your cloud 'cloud01' will expire in 3 days",
            recipients=["user@example.com"],
            priority="high"
        )

    Note:
        To send to specific notifiers only, create a dispatcher instance
        with plugin_names filter:

        dispatcher = NotificationDispatcher(plugin_manager, plugin_names=["slack"])
        dispatcher.send_notification_sync(...)
    """
    dispatcher = get_notification_dispatcher()
    return dispatcher.send_notification_sync(subject, message, recipients, priority, **kwargs)
