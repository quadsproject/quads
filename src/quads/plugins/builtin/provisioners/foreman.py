from src.quads.plugins.interfaces.provisioner import ProvisionerPlugin
from src.quads.config import Config
from src.quads.tools.external.foreman import Foreman
from typing import Any, List


class ForemanProvisionerPlugin(ProvisionerPlugin):
    """Foreman provisioner plugin"""

    def __init__(self):
        self.url = Config.foreman_url
        self.username = Config.foreman_username
        self.password = Config.foreman_password
        self.token = Config.foreman_token
        self.foreman = Foreman(self.url, self.username, self.password, self.token)

    async def prepare_host_provisioning(self, hostname: str, build: bool) -> bool:
        """Prepare host for provisioning"""
        return await self.foreman.prepare_host_provisioning(hostname, build)

    async def mark_for_build(self, hostname: str, build: bool) -> bool:
        """Provision a host"""
        return await self.foreman.mark_for_build(hostname, build)

    async def get_all_hosts(self) -> List[str]:
        """Get all hosts"""
        return await self.foreman.get_all_hosts()

    async def get_host_param(self, hostname: str, param: str) -> Any:
        """Get a host parameter"""
        return await self.foreman.get_host_param(hostname, param)

    async def set_host_param(self, hostname: str, param: str, value: Any) -> bool:
        """Set a host parameter"""
        return await self.foreman.set_host_param(hostname, param, value)
