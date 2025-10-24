import logging
from typing import Optional
from quads.plugins.dispatchers.base import SinglePluginDispatcher
from quads.plugins.interfaces.hardware import HardwarePlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class HardwareDispatcher(SinglePluginDispatcher[HardwarePlugin]):

    def __init__(self, plugin_manager: PluginManager, plugin_name: Optional[str] = None):
        super().__init__(plugin_manager, HardwarePlugin, "Hardware", plugin_name=plugin_name)
        self._runtime_plugin: Optional[HardwarePlugin] = None

    async def init_for_host(self, host: str, rack: str, uloc: str, blade: str) -> bool:
        plugin_class = self._get_plugin_class()
        if not plugin_class:
            logger.error("No hardware plugin enabled")
            return False

        try:
            logger.info(f"Initializing {plugin_class.__name__} for host {host}")
            self._runtime_plugin = plugin_class(host, rack, uloc, blade)
            await self._runtime_plugin.init()
            return True
        except Exception as e:
            logger.error(f"Failed to initialize hardware for {host}: {e}")
            self._runtime_plugin = None
            return False

    def _get_active_plugin(self) -> Optional[HardwarePlugin]:
        return self._runtime_plugin if self._runtime_plugin else self._default_plugin

    async def init(self) -> bool:
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
        plugin = self._get_active_plugin()
        if not plugin:
            logger.error("No hardware plugin enabled")
            return None

        try:
            return plugin.get_hardware_info()
        except Exception as e:
            logger.error(f"Failed to get hardware info: {e}")
            return None


_dispatcher_instance: Optional[HardwareDispatcher] = None


def get_hardware_dispatcher(plugin_manager: Optional[PluginManager] = None) -> HardwareDispatcher:
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize HardwareDispatcher")
        _dispatcher_instance = HardwareDispatcher(plugin_manager)

    return _dispatcher_instance


async def change_boot(boot_order: str, interfaces_path: str) -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.change_boot(boot_order, interfaces_path)


async def set_power_state(state: str) -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.set_power_state(state)


async def reboot_server(graceful: bool = False) -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.reboot_server(graceful)


async def boot_to_type(host_type: str, interfaces_path: str) -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.boot_to_type(host_type, interfaces_path)


async def set_next_boot_pxe() -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.set_next_boot_pxe()


async def unmount_virtual_media() -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.unmount_virtual_media()


async def detach_remote_image() -> bool:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.detach_remote_image()


async def get_power_state() -> Optional[str]:
    dispatcher = get_hardware_dispatcher()
    return await dispatcher.get_power_state()


def get_hardware_info() -> Optional[dict]:
    dispatcher = get_hardware_dispatcher()
    return dispatcher.get_hardware_info()
