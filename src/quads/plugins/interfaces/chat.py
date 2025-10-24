from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional
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
        pass
