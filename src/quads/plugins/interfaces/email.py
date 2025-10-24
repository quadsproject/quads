from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import List, Optional, Dict


class EmailPlugin(BasePlugin):
    """Interface for email notification plugins"""

    @abstractmethod
    async def send_mail(
        self,
        subject: str,
        body: str,
        recipients: List[str],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict]] = None,
        html: bool = True,
        **kwargs,
    ) -> bool:
        pass
