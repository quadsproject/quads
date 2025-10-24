from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional


class EmailPlugin(BasePlugin):
    """Interface for email notification plugins"""

    @abstractmethod
    async def send_mail(
        self,
        subject: str,
        content: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        **kwargs,
    ) -> bool:
        pass
