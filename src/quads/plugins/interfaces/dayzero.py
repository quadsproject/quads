from abc import abstractmethod
from quads.plugins.base import BasePlugin


class DayzeroPlugin(BasePlugin):
    """Interface for post-release day-zero actions on provisioned hosts."""

    @abstractmethod
    async def execute(
        self,
        cloud: str,
    ) -> bool:
        pass
