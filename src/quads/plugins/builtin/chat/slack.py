#!/usr/bin/env python3
"""
Slack Notifier Plugin
"""
import aiohttp
import logging
from typing import List, Optional, Dict, Any
from quads.plugins.interfaces.chat import ChatPlugin, ChatPriority

logger = logging.getLogger(__name__)


class SlackPlugin(ChatPlugin):
    """
    Slack notifier plugin implementing ChatNotifierPlugin interface.

    Also implements NotifierPlugin for backward compatibility.
    """

    name = "slack"
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

    async def send_message(
        self,
        title: str,
        text: str,
        channels: Optional[List[str]] = None,
        priority: ChatPriority = ChatPriority.NORMAL,
        thread_key: Optional[str] = None,
        mentions: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        """
        Send message to Slack using chat-specific features.

        Args:
            title: Message title/header
            text: Message body (supports Slack markdown)
            channels: List of channels (e.g., ["#cloud-ops", "#alerts"])
            priority: Message priority (affects color)
            thread_key: Thread timestamp for threaded replies
            mentions: List of user mentions (e.g., ["@user", "<!channel>"])
        """
        target_channels = channels if channels else [self.default_channel]

        # Map priority enum to Slack colors
        color_map = {
            ChatPriority.LOW: "#808080",  # grey
            ChatPriority.NORMAL: "#36a64f",  # green
            ChatPriority.HIGH: "#ff9900",  # orange
            ChatPriority.URGENT: "#ff0000",  # red
        }
        color = color_map.get(priority, "#36a64f")

        # Add mentions to text if provided
        if mentions:
            mentions_str = " ".join(mentions)
            text = f"{mentions_str}\n{text}"

        success = True
        for channel in target_channels:
            if not await self._send_to_channel(channel, title, text, color, thread_ts=thread_key, **kwargs):
                success = False

        return success

    async def send_card(
        self,
        card_data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        thread_key: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Send a Slack Block Kit card.

        Args:
            card_data: Slack Block Kit JSON structure
            channels: List of channels to send to
            thread_key: Thread timestamp for threaded replies
        """
        target_channels = channels if channels else [self.default_channel]

        payload = {
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            **card_data,
        }

        if thread_key:
            payload["thread_ts"] = thread_key

        success = True
        for channel in target_channels:
            payload["channel"] = channel
            if not await self._send_payload(payload):
                success = False

        return success

    async def send_notification(
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> bool:
        """
        Backward compatibility method - delegates to send_message().

        Args:
            subject: Message title
            message: Message body
            recipients: List of channels
            priority: Priority as string
        """
        # Convert string priority to enum
        priority_map = {
            "low": ChatPriority.LOW,
            "normal": ChatPriority.NORMAL,
            "high": ChatPriority.HIGH,
            "urgent": ChatPriority.URGENT,
        }
        priority_enum = priority_map.get(priority.lower(), ChatPriority.NORMAL)

        return await self.send_message(
            title=subject,
            text=message,
            channels=recipients if recipients else None,
            priority=priority_enum,
            **kwargs,
        )

    async def _send_to_channel(
        self, channel: str, subject: str, message: str, color: str, thread_ts: Optional[str] = None, **kwargs
    ) -> bool:
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

        # Add thread timestamp for threaded replies
        if thread_ts:
            payload["thread_ts"] = thread_ts

        # Add fields if provided
        if "fields" in kwargs:
            payload["attachments"][0]["fields"] = kwargs["fields"]

        return await self._send_payload(payload)

    async def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Send a payload to Slack webhook"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.logger.debug(f"Slack message sent to {payload.get('channel', 'default')}")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Slack webhook failed: {response.status} - {error_text}")
                        return False

        except Exception as e:
            self.logger.error(f"Failed to send Slack notification: {e}")
            return False

    def get_supported_markdown(self) -> Dict[str, bool]:
        """Get Slack markdown support"""
        return {
            "bold": True,
            "italic": True,
            "code": True,
            "lists": True,
            "links": True,
            "tables": False,
            "emoji": True,
        }
