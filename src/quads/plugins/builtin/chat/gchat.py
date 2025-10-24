import aiohttp
from typing import List, Optional, Dict, Any
from quads.plugins.interfaces.chat import ChatPlugin
from quads.plugins.manager import PluginManager


class GoogleChatPlugin(ChatPlugin):
    """
    Google Chat plugin implementing ChatPlugin interface.

    Connects to Google Chat spaces and sends messages to channels.
    """

    name = "gchat"
    version = "1.0.0"
    description = "Send notifications to Google Chat spaces via webhooks"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None) -> bool:
        """Initialize Google Chat webhook connection"""
        self.webhook_url = self.config.get("webhook_url")

        if not self.webhook_url:
            self.logger.error("webhook_url not configured for Google Chat notifier")
            return False

        self.logger.info("Google Chat notifier initialized")
        return True

    async def send_message(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        """
        Send message to Google Chat using chat-specific features.

        Args:
            message: Message body (supports basic markdown)
            channels: Not used for Google Chat (webhook determines space)
        """
        payload = {"text": message}

        return await self._send_payload(payload)

    async def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Send a payload to Google Chat webhook"""
        headers = {"Content-Type": "application/json"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        self.logger.debug("Google Chat message sent")
                        return True
                    else:
                        error_text = await response.text()
                        self.logger.error(f"Google Chat webhook failed: {response.status} - {error_text}")
                        return False

        except Exception as e:
            self.logger.error(f"Failed to send Google Chat notification: {e}")
            return False
