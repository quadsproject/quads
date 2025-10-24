from src.quads.plugins.interfaces.hardware import HardwarePlugin
from src.quads.config import Config
from src.quads.tools.external.badfish import Badfish


class BadfishHardwarePlugin(HardwarePlugin):
    """Badfish hardware plugin"""

    def __init__(self):
        self.ip_address = Config.badfish_ip_address
        self.username = Config.badfish_username
        self.password = Config.badfish_password
        self.token = Config.badfish_token

    def get_hardware_info(self) -> dict:
        """Get hardware information"""
        badfish = Badfish(self.ip_address, self.username, self.password, self.token)
        return badfish.get_hardware_info()
