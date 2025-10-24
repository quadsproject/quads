from quads.plugins.interfaces.provisioner import ProvisionerPlugin
from quads.config import Config
from quads.tools.external.foreman import Foreman
from quads.plugins.manager import PluginManager
from typing import List, Optional


class ForemanProvisionerPlugin(ProvisionerPlugin):
    """
    Foreman provisioner plugin implementing ProvisionerPlugin interface.

    Manages host provisioning through Foreman API.
    """

    name = "foreman"
    version = "1.0.0"
    description = "Foreman provisioner plugin"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.url = self.config.get("api_url")
        self.username = self.config.get("username")
        self.password = self.config.get("password")
        self.token = self.config.get("token")
        self.foreman = Foreman(self.url, self.username, self.password, self.token)
        return True

    async def prepare_host_provisioning(self, hostname: str, build: bool, os_type: str) -> bool:
        """Prepare host for provisioning"""
        return await self.foreman.prepare_host_provisioning(hostname, build, os_type)

    async def get_all_hosts(self) -> List[str]:
        """Get all hosts"""
        return await self.foreman.get_all_hosts()

    async def get_host(self, hostname: str) -> dict:
        """Get host"""
        return await self.foreman.get_host(hostname)

    async def get_images(self) -> List[str]:
        """Get all images"""
        return await self.foreman.get_available_os()
