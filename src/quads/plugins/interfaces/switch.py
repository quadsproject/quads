from src.quads.plugins.base import BasePlugin
from abc import abstractmethod


class SwitchPlugin(BasePlugin):
    """Interface for switch plugins"""

    @abstractmethod
    def get_switch_info(self) -> dict:
        """Get switch information"""
        pass
