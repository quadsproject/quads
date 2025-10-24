from src.quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Optional


class SwitchPlugin(BasePlugin):
    """Interface for switch plugins"""

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the switch.

        Returns:
            bool: True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the connection to the switch"""
        pass

    @abstractmethod
    def execute(self, command: str, expect: Optional[str] = None) -> bool:
        """
        Execute a command on the switch.

        Args:
            command: The command to execute
            expect: Optional string to expect in response

        Returns:
            bool: True if command executed successfully, False otherwise
        """
        pass
