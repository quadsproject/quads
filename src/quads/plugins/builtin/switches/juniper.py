from src.quads.plugins.interfaces.switch import SwitchPlugin
from src.quads.config import Config
from src.quads.tools.external.juniper import Juniper


class JuniperSwitchPlugin(SwitchPlugin):
    """Juniper switch plugin"""

    def __init__(self):
        self.ip_address = Config.juniper_ip_address
        self.username = Config.juniper_username
        self.password = Config.juniper_password
        self.token = Config.juniper_token

    def get_switch_info(self) -> dict:
        """Get switch information"""
        juniper = Juniper(self.ip_address, self.username, self.password, self.token)
        return juniper.get_switch_info()
