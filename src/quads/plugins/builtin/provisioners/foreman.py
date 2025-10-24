from src.quads.plugins.interfaces.provisioner import ProvisionerPlugin
from src.quads.config import Config
from src.quads.tools.external.foreman import Foreman


class ForemanProvisionerPlugin(ProvisionerPlugin):
    """Foreman provisioner plugin"""

    def __init__(self):
        self.url = Config.foreman_url
        self.username = Config.foreman_username
        self.password = Config.foreman_password
        self.token = Config.foreman_token

    def provision_host(self, hostname: str, build: bool) -> bool:
        """Provision a host"""
        foreman = Foreman(self.url, self.username, self.password, self.token)
        return foreman.provision_host(hostname, build)
