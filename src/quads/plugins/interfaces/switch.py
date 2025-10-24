from quads.plugins.base import BasePlugin
from abc import abstractmethod


class SwitchPlugin(BasePlugin):
    """Interface for switch plugins"""

    @abstractmethod
    def configure(self, host: str, old_cloud: str, new_cloud: str) -> bool:
        """
        Configure the switch for the host.

        Args:
            host: Hostname to configure
            old_cloud: Old cloud name
            new_cloud: New cloud name

        Returns:
            bool: True if configuration successful, False otherwise
        """
        pass

    @abstractmethod
    def modify(
        self,
        host: str,
        change: bool = False,
        nic1: str = None,
        nic2: str = None,
        nic3: str = None,
        nic4: str = None,
        nic5: str = None,
    ) -> bool:
        """
        Modify the switch for the host.

        Args:
            host: Hostname to modify
            change: True if change is requested, False otherwise
            nic1: First interface name
            nic2: Second interface name
            nic3: Third interface name
            nic4: Fourth interface name
            nic5: Fifth interface name

        Returns:
            bool: True if modification successful, False otherwise
        """
        pass

    @abstractmethod
    def verify(self, host: str = None, cloud: str = None, change: bool = False) -> bool:
        """
        Verify the switch for the host.

        Args:
            host: Hostname to verify
            cloud: Cloud name to verify
            change: True if change is requested, False otherwise

        Returns:
            bool: True if verification successful, False otherwise
        """
        pass

    @abstractmethod
    def ls_config(self, cloud: str, all: bool = False) -> bool:
        """
        List the switch configuration for the cloud.

        Args:
            cloud: Cloud name to list configuration for
            all: True if all configuration is requested, False otherwise

        Returns:
            bool: True if listing successful, False otherwise
        """
        pass
