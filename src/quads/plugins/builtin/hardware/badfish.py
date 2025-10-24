from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.tools.external.badfish import Badfish, badfish_factory, BadfishException
from quads.plugins.manager import PluginManager
from typing import Optional


class BadfishHardwarePlugin(HardwarePlugin):
    """
    Badfish hardware plugin for Redfish-based hardware management

    Manages hardware operations using Redfish API.
    """

    name = "badfish"
    version = "1.0.0"
    description = "Badfish hardware plugin for Redfish-based hardware management"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        """
        Initialize Badfish plugin.
        """
        self.username = self.config.get("ipmi_username", "")
        self.password = self.config.get("ipmi_password", "")
        self.badfish: Optional[Badfish] = None
        return True

    async def init(self, host: str, rack: str, uloc: str, blade: str) -> None:
        """Initialize the Badfish connection"""
        self.host = host
        self.rack = rack
        self.uloc = uloc
        self.blade = blade
        try:
            self.badfish = await badfish_factory(
                f"mgmt-{host}",
                rack,
                uloc,
                blade,
                self.username,
                self.password,
                propagate=True,
            )
        except BadfishException as e:
            self.logger.error(f"Failed to initialize Badfish for {self.host}: {e}")
            raise

    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        """Change the boot order configuration"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.change_boot(boot_order, interfaces_path)
        except BadfishException as e:
            self.logger.error(f"Failed to change boot order: {e}")
            return False

    async def set_power_state(self, state: str) -> None:
        """Set the power state of the hardware"""
        if not self.badfish:
            raise BadfishException("Badfish not initialized")

        await self.badfish.set_power_state(state)

    async def unmount_virtual_media(self) -> bool:
        """Unmount any mounted virtual media"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.unmount_virtual_media()
        except BadfishException as e:
            self.logger.error(f"Failed to unmount virtual media: {e}")
            return False

    async def detach_remote_image(self) -> bool:
        """Detach remote ISO image"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.detach_remote_image()
        except BadfishException as e:
            self.logger.error(f"Failed to detach remote image: {e}")
            return False

    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """Boot to a specific host type configuration"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return False

        try:
            await self.badfish.boot_to_type(host_type, interfaces_path)
            return True
        except BadfishException as e:
            self.logger.error(f"Failed to boot to type: {e}")
            return False

    async def reboot_server(self, graceful: bool = False) -> bool:
        """Reboot the server"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return False

        try:
            return await self.badfish.reboot_server(graceful=graceful)
        except BadfishException as e:
            self.logger.error(f"Failed to reboot server: {e}")
            return False

    async def set_next_boot_pxe(self) -> None:
        """Set the next boot to PXE"""
        if not self.badfish:
            raise BadfishException("Badfish not initialized")

        await self.badfish.set_next_boot_pxe()

    async def get_power_state(self) -> str:
        """Get the current power state of the hardware"""
        if not self.badfish:
            self.logger.error("Badfish not initialized")
            return "Unknown"

        try:
            return await self.badfish.get_power_state()
        except BadfishException as e:
            self.logger.error(f"Failed to get power state: {e}")
            return "Unknown"
