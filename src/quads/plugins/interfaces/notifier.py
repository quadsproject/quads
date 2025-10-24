# src/quads/plugins/interfaces/notifier.py
from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List


class NotifierPlugin(BasePlugin):
    """Interface for notification plugins"""

    @abstractmethod
    async def send_notification(self, subject: str, message: str, recipients: List[str], **kwargs) -> bool:
        """Send a notification"""
        pass
