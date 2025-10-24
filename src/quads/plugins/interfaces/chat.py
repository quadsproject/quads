from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional


class ChatPlugin(BasePlugin):
    """Interface for chat/messaging notification plugins (Slack, Google Chat, Teams, etc.)"""

    @abstractmethod
    async def send_message(
        self,
        message: str,
        channels: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        pass
