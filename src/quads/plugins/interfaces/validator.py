from src.quads.plugins.base import BasePlugin
from abc import abstractmethod


class ValidatorPlugin(BasePlugin):
    """Interface for validator plugins"""

    @abstractmethod
    def validate(self, hostname: str) -> bool:
        """Validate a hostname"""
        pass
