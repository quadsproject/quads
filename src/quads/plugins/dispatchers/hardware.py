#!/usr/bin/env python3
"""
Hardware Dispatcher - Automatically routes to enabled hardware plugin

Uses SinglePluginDispatcher because hardware operations should only
be executed via ONE plugin at a time (e.g., don't reboot via both
Badfish and iDRAC simultaneously).
"""
import logging
from typing import Optional
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class HardwareDispatcher(SinglePluginDispatcher[HardwarePlugin]):
    """
    Dispatches hardware operations to the enabled hardware plugin.

    Core code calls generic methods without knowing if it's
    Badfish, iDRAC, iLO, etc.

    This is a SinglePluginDispatcher - only ONE hardware plugin is used at a time.

    Plugin Selection:
    - By default, uses the first enabled hardware plugin
    - Can specify plugin_name at initialization to use a specific plugin
    - Useful for testing, debugging, or explicit plugin selection

    Example:
        # Use default hardware plugin
        dispatcher = HardwareDispatcher(plugin_manager)

        # Use specific hardware plugin
        dispatcher = HardwareDispatcher(plugin_manager, plugin_name="ilo")
    """

    def __init__(self, plugin_manager: PluginManager, plugin_name: Optional[str] = None):
        super().__init__(plugin_manager, HardwarePlugin, "Hardware", plugin_name=plugin_name)

    async def init(self) -> bool:
        """
        Initialize the hardware plugin connection.

        Core code doesn't need to know the hardware type.
        """
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Initializing hardware via {self._default_plugin.name}")
        try:
            await self._default_plugin.init()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            return False

    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        """
        Change the boot order configuration.

        Core code doesn't need to know the hardware management interface.
        """
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Changing boot order to {boot_order} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.change_boot(boot_order, interfaces_path)
        except Exception as e:
            logger.error(f"Failed to change boot order: {e}")
            return False

    async def set_power_state(self, state: str) -> bool:
        """
        Set the power state of the hardware.
        """
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Setting power state to {state} via {self._default_plugin.name}")
        try:
            await self._default_plugin.set_power_state(state)
            return True
        except Exception as e:
            logger.error(f"Failed to set power state: {e}")
            return False

    async def unmount_virtual_media(self) -> bool:
        """Unmount any mounted virtual media"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Unmounting virtual media via {self._default_plugin.name}")
        try:
            return await self._default_plugin.unmount_virtual_media()
        except Exception as e:
            logger.error(f"Failed to unmount virtual media: {e}")
            return False

    async def detach_remote_image(self) -> bool:
        """Detach remote ISO image"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Detaching remote image via {self._default_plugin.name}")
        try:
            return await self._default_plugin.detach_remote_image()
        except Exception as e:
            logger.error(f"Failed to detach remote image: {e}")
            return False

    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """Boot to a specific host type configuration"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Booting to type {host_type} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.boot_to_type(host_type, interfaces_path)
        except Exception as e:
            logger.error(f"Failed to boot to type: {e}")
            return False

    async def reboot_server(self, graceful: bool = False) -> bool:
        """
        Reboot the server.

        Args:
            graceful: If True, perform graceful shutdown before reboot

        Returns:
            True if reboot succeeded, False otherwise
        """
        plugin = self.get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        reboot_type = "graceful" if graceful else "forced"
        logger.info(f"Performing {reboot_type} reboot via {plugin.name}")
        try:
            return await plugin.reboot_server(graceful)
        except Exception as e:
            logger.error(f"Failed to reboot server: {e}")
            return False

    async def set_next_boot_pxe(self) -> bool:
        """Set the next boot to PXE"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Setting next boot to PXE via {self._default_plugin.name}")
        try:
            await self._default_plugin.set_next_boot_pxe()
            return True
        except Exception as e:
            logger.error(f"Failed to set next boot to PXE: {e}")
            return False

    async def get_power_state(self) -> Optional[str]:
        """Get the current power state"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return None

        try:
            return await self._default_plugin.get_power_state()
        except Exception as e:
            logger.error(f"Failed to get power state: {e}")
            return None

    def get_hardware_info(self) -> Optional[dict]:
        """Get hardware information"""
        if not self._default_plugin:
            logger.error("No hardware plugin enabled")
            return None

        try:
            return self._default_plugin.get_hardware_info()
        except Exception as e:
            logger.error(f"Failed to get hardware info: {e}")
            return None


# Singleton instance
_dispatcher_instance: Optional[HardwareDispatcher] = None


def get_hardware_dispatcher(plugin_manager: Optional[PluginManager] = None) -> HardwareDispatcher:
    """
    Get the global HardwareDispatcher instance (uses default plugin).

    This singleton always uses the default (first enabled) hardware plugin.
    To use a specific plugin, create a dispatcher instance directly:

        dispatcher = HardwareDispatcher(plugin_manager, plugin_name="ilo")

    Args:
        plugin_manager: PluginManager instance (required on first call)

    Returns:
        HardwareDispatcher singleton instance
    """
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize HardwareDispatcher")
        _dispatcher_instance = HardwareDispatcher(plugin_manager)

    return _dispatcher_instance


# Convenience functions
async def change_boot(boot_order: str, interfaces_path: str) -> bool:
    """
    Change the boot order configuration.

    Example:
        from quads.plugins.hardware_dispatcher import change_boot

        # Works with any hardware management interface (Badfish, iDRAC, iLO, etc.)
        await change_boot("foreman", "/opt/quads/conf/idrac_interfaces.yml")
    """
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.change_boot(boot_order, interfaces_path)


async def set_power_state(state: str) -> bool:
    """Set power state (on/off)"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.set_power_state(state)


async def reboot_server(graceful: bool = False) -> bool:
    """Reboot the server"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.reboot_server(graceful)


async def boot_to_type(host_type: str, interfaces_path: str) -> bool:
    """Boot to a specific host type"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.boot_to_type(host_type, interfaces_path)


async def set_next_boot_pxe() -> bool:
    """Set next boot to PXE"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.set_next_boot_pxe()


async def unmount_virtual_media() -> bool:
    """Unmount virtual media"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.unmount_virtual_media()


async def detach_remote_image() -> bool:
    """Detach remote ISO image"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.detach_remote_image()


async def get_power_state() -> Optional[str]:
    """Get current power state"""
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.get_power_state()


def get_hardware_info() -> Optional[dict]:
    """Get hardware information"""
    dispatcher = get_hardware_dispatcher()
    return dispatcher.get_hardware_info()
