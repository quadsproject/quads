#!/usr/bin/env python3
"""
Google Chat Notifier Plugin
"""
import aiohttp
import logging
from typing import List
from quads.plugins.interfaces.notifier import NotifierPlugin

logger = logging.getLogger(__name__)


class GoogleChatNotifierPlugin(NotifierPlugin):
    """Send notifications to Google Chat via webhook"""

    name = "gchat_notifier"
    version = "1.0.0"
    description = "Send notifications to Google Chat spaces via webhooks"
    author = "QUADS Team"

    def initialize(self) -> bool:
        """Initialize Google Chat webhook connection"""
        self.webhook_url = self.config.get("webhook_url")
        self.thread_key = self.config.get("thread_key")  # Optional: keep conversations threaded

        if not self.webhook_url:
            self.logger.error("webhook_url not configured for Google Chat notifier")
            return False

        self.logger.info("Google Chat notifier initialized")
        return True

    def shutdown(self) -> None:
        """Cleanup resources"""
        pass

    def health_check(self) -> bool:
        """Check if webhook is accessible"""
        return bool(self.webhook_url)

    async def send_notification(
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> bool:
        """
        Send notification to Google Chat.

        Args:
            subject: Message header/title
            message: Message body (supports basic markdown)
            recipients: Not used for Google Chat (webhook determines space)
            priority: Affects message formatting
        """
        # Build Google Chat card message
        payload = {
            "cards": [
                {
                    "header": {
                        "title": subject,
                        "subtitle": f"Priority: {priority.upper()}",
                        "imageUrl": "https://developers.google.com/chat/images/quickstart-app-avatar.png",
                    },
                    "sections": [{"widgets": [{"textParagraph": {"text": message}}]}],
                }
            ]
        }

        # Add thread key if configured for threaded conversations
        if self.thread_key:
            payload["thread"] = {"threadKey": self.thread_key}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
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
