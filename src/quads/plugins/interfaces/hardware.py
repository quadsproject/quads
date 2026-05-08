from quads.plugins.base import BasePlugin
from abc import abstractmethod
from typing import Optional


class HardwarePlugin(BasePlugin):
    """Interface for hardware plugins (e.g., Badfish/Redfish)"""

    @abstractmethod
    async def init(self, host: str, rack: str, uloc: str, blade: str) -> None:
        """
        Initialize the hardware plugin connection and resources.
        Should be called after instantiation.
        """
        pass

    @abstractmethod
    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        """
        Change the boot order configuration.

        Args:
            boot_order: The boot order type/configuration to set
            interfaces_path: Path to the interfaces configuration file

        Returns:
            bool: True if boot order changed successfully, False otherwise
        """
        pass

    @abstractmethod
    async def set_power_state(self, state: str) -> None:
        """
        Set the power state of the hardware.

        Args:
            state: Power state to set ('on' or 'off')

        Raises:
            Exception: If power state change fails
        """
        pass

    @abstractmethod
    async def unmount_virtual_media(self) -> bool:
        """
        Unmount any mounted virtual media.

        Returns:
            bool: True if unmount successful, False otherwise
        """
        pass

    @abstractmethod
    async def detach_remote_image(self) -> bool:
        """
        Detach remote ISO image.

        Returns:
            bool: True if detach successful, False otherwise
        """
        pass

    @abstractmethod
    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """
        Boot to a specific host type configuration.

        Args:
            host_type: The host type to boot to (e.g., 'foreman')
            interfaces_path: Path to the interfaces configuration file

        Returns:
            bool: True if boot configuration successful, False otherwise
        """
        pass

    @abstractmethod
    async def reboot_server(self, graceful: bool = False) -> bool:
        """
        Reboot the server.

        Args:
            graceful: If True, perform graceful reboot; if False, force reboot

        Returns:
            bool: True if reboot successful, False otherwise
        """
        pass

    @abstractmethod
    async def set_next_boot_pxe(self) -> None:
        """
        Set the next boot to PXE.

        Raises:
            Exception: If setting PXE boot fails
        """
        pass

    @abstractmethod
    async def get_power_state(self) -> str:
        """
        Get the current power state of the hardware.

        Returns:
            str: Current power state ('On', 'Off', 'Down', etc.)
        """
        pass

    def get_vendor(self) -> Optional[str]:
        """Return the hardware vendor string after init(), or None if unavailable.

        Hardware plugins should override this to return the correct vendor so that
        Dell-specific boot paths (boot_to_type, change_boot) are taken. Plugins that
        do not override this return None and will use the non-Dell (PXE) path.
        """
        return None
