from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Any


class ProvisionerPlugin(BasePlugin):
    """Interface for provisioning backend plugins"""

    @abstractmethod
    async def provision_host(self, hostname: str, build: bool) -> bool:
        pass

    @abstractmethod
    async def get_host_param(self, hostname: str, param: str) -> Any:
        pass
