from quads.plugins.base import BasePlugin
from abc import abstractmethod
import asyncio
from typing import Optional


class ReleasePlugin(BasePlugin):
    """Interface for host release/rebuild plugins"""

    @abstractmethod
    async def move_and_rebuild(
        self,
        host: str,
        new_cloud: str,
        semaphore: asyncio.Semaphore,
        rebuild: bool = False,
        schedule_id: Optional[int] = None,
    ) -> bool:
        """
        Move a host to a new cloud and optionally rebuild it.

        Args:
            host: Hostname to move
            new_cloud: Target cloud name
            semaphore: Async semaphore for concurrency control
            rebuild: Whether to rebuild the host
            schedule_id: Optional Schedule ID for progress tracking

        Returns:
            bool: True if move/rebuild successful, False otherwise
        """
        pass
