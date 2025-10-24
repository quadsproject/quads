from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional, Dict, Any
from enum import Enum


class ChatPriority(Enum):
    """Priority levels for chat messages (affects visual presentation)"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ChatPlugin(BasePlugin):
    """Interface for chat/messaging notification plugins (Slack, Google Chat, Teams, etc.)"""

    @abstractmethod
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
        Send a chat message.

        Args:
            title: Message title/header
            text: Message body (supports platform-specific markdown)
            channels: List of channels/spaces to send to (uses default if None)
            priority: Message priority (affects color/visual treatment)
            thread_key: Optional thread identifier for threaded conversations
            mentions: Optional list of user IDs or @mentions
            **kwargs: Platform-specific parameters (buttons, fields, etc.)

        Returns:
            bool: True if message sent successfully, False otherwise

        Example:
            await chat_notifier.send_message(
                title="Cloud Assignment Ending",
                text="Your cloud `cloud01` will expire in 3 days",
                channels=["#cloud-ops"],
                priority=ChatPriority.HIGH,
                mentions=["@user"]
            )
        """
        pass

    @abstractmethod
    async def send_card(
        self,
        card_data: Dict[str, Any],
        channels: Optional[List[str]] = None,
        thread_key: Optional[str] = None,
        **kwargs,
    ) -> bool:
        """
        Send a rich card message (platform-specific format).

        This allows full control over the message structure using the
        platform's native card/block format.

        Args:
            card_data: Platform-specific card/block data structure
            channels: List of channels/spaces to send to
            thread_key: Optional thread identifier
            **kwargs: Additional platform-specific parameters

        Returns:
            bool: True if card sent successfully, False otherwise

        Example:
            # Slack blocks
            await slack.send_card(
                card_data={
                    "blocks": [
                        {"type": "header", "text": {"type": "plain_text", "text": "Alert"}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": "Cloud expiring"}}
                    ]
                },
                channels=["#alerts"]
            )

            # Google Chat card
            await gchat.send_card(
                card_data={
                    "cards": [{
                        "header": {"title": "Alert"},
                        "sections": [{"widgets": [{"textParagraph": {"text": "Cloud expiring"}}]}]
                    }]
                }
            )
        """
        pass

    @abstractmethod
    async def send_notification(
        self,
        title: str,
        text: str,
        channels: Optional[List[str]] = None,
        priority: str = "normal",
        **kwargs,
    ) -> bool:
        """
        Backward compatibility method - maps to send_message().

        This maintains compatibility with the old NotifierPlugin interface.
        New code should use send_message() instead.

        Args:
            title: Message title/header
            text: Message body
            channels: List of channels (replaces 'recipients' from old interface)
            priority: Priority as string
            **kwargs: Additional parameters

        Returns:
            bool: True if sent successfully, False otherwise
        """
        pass

    def get_supported_markdown(self) -> Dict[str, bool]:
        """
        Get markdown features supported by this chat platform.

        Returns:
            Dictionary mapping feature names to support status

        Example:
            {
                "bold": True,
                "italic": True,
                "code": True,
                "lists": True,
                "tables": False,
                "emoji": True,
            }
        """
        return {
            "bold": True,
            "italic": True,
            "code": True,
            "lists": True,
            "links": True,
            "tables": False,
            "emoji": False,
        }
