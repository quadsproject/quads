from src.quads.plugins.interfaces.hardware import HardwarePlugin
from src.quads.config import Config
from src.quads.tools.external.badfish import Badfish, badfish_factory, BadfishException
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BadfishHardwarePlugin(HardwarePlugin):
    """Badfish hardware plugin for Redfish-based hardware management"""

    def __init__(self, host: str, rack: str, uloc: str, blade: str):
        """
        Initialize Badfish plugin.

        Args:
            host: Hostname or IP address
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier
        """
        self.host = host
        self.rack = rack
        self.uloc = uloc
        self.blade = blade
        self.username = Config.get("ipmi_username", "")
        self.password = Config.get("ipmi_password", "")
        self.badfish: Optional[Badfish] = None

    async def init(self) -> None:
        """Initialize the Badfish connection"""
        try:
            self.badfish = await badfish_factory(
                f"mgmt-{self.host}",
                self.rack,
                self.uloc,
                self.blade,
                self.username,
                self.password,
                propagate=True,
            )
        except BadfishException as e:
            logger.error(f"Failed to initialize Badfish for {self.host}: {e}")
            raise

    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        """Change the boot order configuration"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.change_boot(boot_order, interfaces_path)
        except BadfishException as e:
            logger.error(f"Failed to change boot order: {e}")
            return False

    async def set_power_state(self, state: str) -> None:
        """Set the power state of the hardware"""
        if not self.badfish:
            raise BadfishException("Badfish not initialized")

        await self.badfish.set_power_state(state)

    async def unmount_virtual_media(self) -> bool:
        """Unmount any mounted virtual media"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.unmount_virtual_media()
        except BadfishException as e:
            logger.error(f"Failed to unmount virtual media: {e}")
            return False

    async def detach_remote_image(self) -> bool:
        """Detach remote ISO image"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.detach_remote_image()
        except BadfishException as e:
            logger.error(f"Failed to detach remote image: {e}")
            return False

    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """Boot to a specific host type configuration"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return False

        try:
            await self.badfish.boot_to_type(host_type, interfaces_path)
            return True
        except BadfishException as e:
            logger.error(f"Failed to boot to type: {e}")
            return False

    async def reboot_server(self, graceful: bool = False) -> bool:
        """Reboot the server"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.reboot_server(graceful=graceful)
        except BadfishException as e:
            logger.error(f"Failed to reboot server: {e}")
            return False

    async def set_next_boot_pxe(self) -> None:
        """Set the next boot to PXE"""
        if not self.badfish:
            raise BadfishException("Badfish not initialized")

        await self.badfish.set_next_boot_pxe()

    async def get_power_state(self) -> str:
        """Get the current power state of the hardware"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return "Unknown"

        try:
            return await self.badfish.get_power_state()
        except BadfishException as e:
            logger.error(f"Failed to get power state: {e}")
            return "Unknown"

    def get_hardware_info(self) -> dict:
        """Get hardware information"""
        if not self.badfish:
            logger.error("Badfish not initialized")
            return {}

        # Return basic info about the badfish connection
        return {
            "host": self.host,
            "rack": self.rack,
            "uloc": self.uloc,
            "blade": self.blade,
            "vendor": self.badfish.vendor if self.badfish.vendor else "Unknown",
            "system_resource": self.badfish.system_resource if self.badfish.system_resource else None,
            "manager_resource": self.badfish.manager_resource if self.badfish.manager_resource else None,
        }
