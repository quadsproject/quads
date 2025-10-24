import aiohttp
from typing import List, Optional, Dict, Any
from quads.plugins.interfaces.chat import ChatPlugin


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

    async def send_message(
        self,
        title: str,
        text: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        """
        Send message to Slack using chat-specific features.

        Args:
            title: Message title/header
            text: Message body (supports Slack markdown)
            channels: List of channels (e.g., ["#cloud-ops", "#alerts"])
        """
        target_channels = channels if channels else [self.default_channel]

        success = True
        for channel in target_channels:
            if not await self._send_to_channel(channel, title, text, **kwargs):
                success = False

        return success

    async def _send_to_channel(self, channel: str, subject: str, message: str, **kwargs) -> bool:
        """Send message to a specific Slack channel"""

        # Build Slack message payload
        payload = {
            "channel": channel,
            "username": self.username,
            "icon_emoji": self.icon_emoji,
            "attachments": [
                {
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
