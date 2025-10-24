from src.quads.plugins.base import BasePlugin
from abc import abstractmethod


class HardwarePlugin(BasePlugin):
    """Interface for hardware plugins"""

    @abstractmethod
    def get_hardware_info(self) -> dict:
        """Get hardware information"""
        pass
