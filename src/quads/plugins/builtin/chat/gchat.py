#!/usr/bin/env python3
"""
Google Chat Notifier Plugin
"""
import aiohttp
import logging
from typing import List, Optional, Dict, Any
from quads.plugins.interfaces.chat import ChatPlugin, ChatPriority

logger = logging.getLogger(__name__)


class GoogleChatPlugin(ChatPlugin):
    name = "gchat"
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
        Send message to Google Chat using chat-specific features.

        Args:
            title: Message header/title
            text: Message body (supports basic markdown)
            channels: Not used for Google Chat (webhook determines space)
            priority: Message priority (affects visual presentation)
            thread_key: Thread key for threaded conversations
            mentions: List of user mentions (e.g., ["<users/123>"])
        """
        # Add mentions to text if provided
        if mentions:
            mentions_str = " ".join(mentions)
            text = f"{mentions_str}\n{text}"

        # Build Google Chat card message
        payload = {
            "cards": [
                {
                    "header": {
                        "title": title,
                        "subtitle": f"Priority: {priority.value.upper()}",
                        "imageUrl": self._get_priority_icon(priority),
                    },
                    "sections": [{"widgets": [{"textParagraph": {"text": text}}]}],
                }
            ]
        }

        # Add thread key for threaded conversations
        thread_key_to_use = thread_key or self.thread_key
        if thread_key_to_use:
            payload["thread"] = {"threadKey": thread_key_to_use}

        return await self._send_payload(payload)

    async def send_card(
        self,
        card_data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        thread_key: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Send a Google Chat Card (v2) message.

        Args:
            card_data: Google Chat Card JSON structure
            channels: Not used (webhook determines space)
            thread_key: Thread key for threaded conversations
        """
        payload = card_data.copy()

        # Add thread key if provided
        thread_key_to_use = thread_key or self.thread_key
        if thread_key_to_use and "thread" not in payload:
            payload["thread"] = {"threadKey": thread_key_to_use}

        return await self._send_payload(payload)

    async def send_notification(
        self, subject: str, message: str, recipients: List[str], priority: str = "normal", **kwargs
    ) -> bool:
        """
        Backward compatibility method - delegates to send_message().

        Args:
            subject: Message title
            message: Message body
            recipients: Not used for Google Chat
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
            priority=priority_enum,
            **kwargs,
        )

    async def _send_payload(self, payload: Dict[str, Any]) -> bool:
        """Send a payload to Google Chat webhook"""
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

    def _get_priority_icon(self, priority: ChatPriority) -> str:
        """Get icon URL based on priority"""
        icon_map = {
            ChatPriority.LOW: "https://developers.google.com/chat/images/quickstart-app-avatar.png",
            ChatPriority.NORMAL: "https://developers.google.com/chat/images/quickstart-app-avatar.png",
            ChatPriority.HIGH: "https://www.gstatic.com/images/icons/material/system/2x/warning_amber_24dp.png",
            ChatPriority.URGENT: "https://www.gstatic.com/images/icons/material/system/2x/error_outline_red_24dp.png",
        }
        return icon_map.get(priority, icon_map[ChatPriority.NORMAL])

    def get_supported_markdown(self) -> Dict[str, bool]:
        """Get Google Chat markdown support"""
        return {
            "bold": True,
            "italic": True,
            "code": True,
            "lists": False,
            "links": True,
            "tables": False,
            "emoji": False,
        }
