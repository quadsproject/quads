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

        # Initialize for specific host
        await dispatcher.init_for_host(host="host01", rack="r01", uloc="u01", blade="b01")

        # Use specific hardware plugin
        dispatcher = HardwareDispatcher(plugin_manager, plugin_name="ilo")
    """

    def __init__(self, plugin_manager: PluginManager, plugin_name: Optional[str] = None):
        super().__init__(plugin_manager, HardwarePlugin, "Hardware", plugin_name=plugin_name)
        self._runtime_plugin: Optional[HardwarePlugin] = None

    async def init_for_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        """
        Initialize a hardware plugin instance for a specific host.

        This creates a new plugin instance with host-specific parameters.
        The dispatcher automatically selects the appropriate plugin based on config.

        Args:
            host: Hostname or IP address
            rack: Rack identifier
            uloc: Location identifier
            blade: Blade identifier

        Returns:
            bool: True if initialization succeeded, False otherwise

        Example:
            dispatcher = HardwareDispatcher(plugin_manager)
            if await dispatcher.init_for_host("host01", "r01", "u01", "b01"):
                await dispatcher.reboot_server()
        """
        # Get the plugin class (not instance) to create a new instance
        plugin_class = self._get_plugin_class()
        if not plugin_class:
            logger.error("No hardware plugin enabled")
            return False

        try:
            # Instantiate the plugin with host-specific args
            logger.info(f"Initializing {plugin_class.__name__} for host {host}")
            self._runtime_plugin = plugin_class(host, rack, uloc, blade)
            await self._runtime_plugin.init()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize hardware for {host}: {e}")
            self._runtime_plugin = None
            return False

    def _get_active_plugin(self) -> Optional[HardwarePlugin]:
        """Get the active plugin instance (runtime instance if available, otherwise default)"""
        return self._runtime_plugin if self._runtime_plugin else self._default_plugin

    async def init(self) -> bool:
        """
        Initialize the hardware plugin connection.

        Core code doesn't need to know the hardware type.

        Note: For host-specific operations, use init_for_host() instead.
        """
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Initializing hardware via {plugin.name}")
        try:
            await plugin.init()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize hardware: {e}")
            return False

    async def change_boot(self, boot_order: str, interfaces_path: str) -> bool:
        """
        Change the boot order configuration.

        Core code doesn't need to know the hardware management interface.
        """
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Changing boot order to {boot_order} via {plugin.name}")
        try:
            return await plugin.change_boot(boot_order, interfaces_path)
        except Exception as e:
            logger.error(f"Failed to change boot order: {e}")
            return False

    async def set_power_state(self, state: str) -> bool:
        """
        Set the power state of the hardware.
        """
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Setting power state to {state} via {plugin.name}")
        try:
            await plugin.set_power_state(state)
            return True
        except Exception as e:
            logger.error(f"Failed to set power state: {e}")
            return False

    async def unmount_virtual_media(self) -> bool:
        """Unmount any mounted virtual media"""
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Unmounting virtual media via {plugin.name}")
        try:
            return await plugin.unmount_virtual_media()
        except Exception as e:
            logger.error(f"Failed to unmount virtual media: {e}")
            return False

    async def detach_remote_image(self) -> bool:
        """Detach remote ISO image"""
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Detaching remote image via {plugin.name}")
        try:
            return await plugin.detach_remote_image()
        except Exception as e:
            logger.error(f"Failed to detach remote image: {e}")
            return False

    async def boot_to_type(self, host_type: str, interfaces_path: str) -> bool:
        """Boot to a specific host type configuration"""
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Booting to type {host_type} via {plugin.name}")
        try:
            return await plugin.boot_to_type(host_type, interfaces_path)
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
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return False

        logger.info(f"Setting next boot to PXE via {plugin.name}")
        try:
            await plugin.set_next_boot_pxe()
            return True
        except Exception as e:
            logger.error(f"Failed to set next boot to PXE: {e}")
            return False

    async def get_power_state(self) -> Optional[str]:
        """Get the current power state"""
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return None

        try:
            return await plugin.get_power_state()
        except Exception as e:
            logger.error(f"Failed to get power state: {e}")
            return None

    def get_hardware_info(self) -> Optional[dict]:
        """Get hardware information"""
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return None

        try:
            return plugin.get_hardware_info()
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
