#!/usr/bin/env python3
"""
Slack Notifier Plugin
"""
import aiohttp
import logging
from typing import List
from quads.plugins.interfaces.notifier import NotifierPlugin

logger = logging.getLogger(__name__)


class SlackNotifierPlugin(NotifierPlugin):
    """Send notifications to Slack via webhook"""

    name = "slack_notifier"
    version = "1.0.0"
    description = "Send notifications to Slack channels via webhooks"
    author = "QUADS Team"

    def initialize(self) -> bool:
        """Initialize Slack webhook connection"""
        self.webhook_url = self.config.get("webhook_url")
        self.default_channel = self.config.get("default_channel", "#quads")
        self.username = self.config.get("username", "QUADS Bot")
        self.icon_emoji = self.config.get("icon_emoji", ":robot_face:")

        if not self.webhook_url:
            self.logger.error("webhook_url not configured for Slack notifier")
            return False

        self.logger.info(f"Slack notifier initialized (channel: {self.default_channel})")
        return True

    def shutdown(self) -> None:
        """Cleanup resources"""
        pass

    def health_check(self) -> bool:
        """Check if webhook is accessible"""
        # Could do a test POST here, but webhooks don't have a health endpoint
        return bool(self.webhook_url)

    async def send_notification(
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> bool:
        """
        Send notification to Slack.

        Args:
            subject: Will be used as the message title/header
            message: Message body (supports markdown)
            recipients: List of channels (e.g., ["#cloud-ops", "#alerts"])
                       If empty, uses default_channel
            priority: Affects message color (low=grey, normal=blue, high=orange, urgent=red)
        """
        channels = recipients if recipients else [self.default_channel]

        # Map priority to Slack colors
        color_map = {
            "low": "#808080",  # grey
            "normal": "#36a64f",  # green
            "high": "#ff9900",  # orange
            "urgent": "#ff0000",  # red
        }
        color = color_map.get(priority, "#36a64f")

        success = True
        for channel in channels:
            if not await self._send_to_channel(channel, subject, message, color, **kwargs):
                success = False

        return success

    async def _send_to_channel(self, channel: str, subject: str, message: str, color: str, **kwargs) -> bool:
        """Send message to a specific Slack channel"""

        # Build Slack message payload
        payload = {
            "channel": channel,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
                    "color": color,
                    "title": subject,
                    "text": message,
                    "footer": "QUADS Notification System",
                    "ts": kwargs.get("timestamp", None),
                }
            ],
        }

        # Add fields if provided
        if "fields" in kwargs:
            payload["attachments"][0]["fields"] = kwargs["fields"]

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.logger.debug(f"Slack message sent to {channel}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Slack webhook failed: {response.status} - {error_text}")
                        return False

        except Exception as e:
            self.logger.error(f"Failed to send Slack notification: {e}")
            return False
