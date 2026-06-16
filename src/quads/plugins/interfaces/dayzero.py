from abc import abstractmethod
from typing import List, Union
from quads.plugins.base import BasePlugin


class DayzeroPlugin(BasePlugin):
    """Interface for post-release day-zero actions on provisioned hosts."""

    @abstractmethod
    async def execute(
        self,
        host: Union[str, List[str]],
        cloud: str,
    ) -> bool:
        pass
