from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Any, List


class ProvisionerPlugin(BasePlugin):
    """Interface for provisioning backend plugins"""

    @abstractmethod
    async def prepare_host_provisioning(self, host_name: str, cloud: str, os_type: str) -> bool:
        pass

    @abstractmethod
    async def get_all_hosts(self) -> List[str]:
        pass

    @abstractmethod
    async def get_images(self) -> List[str]:
        pass
