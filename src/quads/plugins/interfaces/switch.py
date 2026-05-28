from typing import Optional

from quads.plugins.base import BasePlugin
from abc import abstractmethod


class SwitchPlugin(BasePlugin):
    """Interface for switch plugins"""

    # Interfaces with no switch_vendor belong to the plugin that declares
    # this True (the historical default), so only one plugin ever programs them.
    _owns_legacy_interfaces = False

    def owns_interface(self, interface) -> bool:
        """True if this plugin is responsible for the interface."""
        vendor = getattr(interface, "switch_vendor", None)
        return vendor == self.name or (vendor is None and self._owns_legacy_interfaces)

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
        overrides: Optional[dict] = None,
    ) -> bool:
        """
        Modify the switch for the host.

        Args:
            host: Hostname to modify
            change: True if change is requested, False otherwise
            overrides: Dict mapping interface index (int) to VLAN ID (str)

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
