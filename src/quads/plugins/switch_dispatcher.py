#!/usr/bin/env python3
"""
Switch Dispatcher - Automatically routes to enabled switch vendor plugin
"""
import logging
from typing import Optional, List
from quads.plugins.base_dispatcher import BaseDispatcher
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.plugins.manager import PluginManager

logger = logging.getLogger(__name__)


class SwitchDispatcher(BaseDispatcher[SwitchPlugin]):
    """
    Dispatches network switch operations to the enabled switch plugin.

    Core code calls generic methods without knowing if it's
    Juniper, Arista, Cisco, etc.
    """

    def __init__(self, plugin_manager: PluginManager):
        super().__init__(plugin_manager, SwitchPlugin, "Switch")

    async def set_port_vlan(self, switch: str, port: str, vlan: int, native: bool = False) -> bool:
        """
        Configure VLAN on a switch port.

        Core code doesn't need to know the switch vendor.
        """
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        logger.info(f"Setting VLAN {vlan} on {switch}:{port} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.set_port_vlan(switch, port, vlan, native)
        except Exception as e:
            logger.error(f"Failed to set VLAN: {e}")
            return False

    async def remove_port_vlan(self, switch: str, port: str, vlan: int) -> bool:
        """Remove VLAN from switch port"""
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        logger.info(f"Removing VLAN {vlan} from {switch}:{port} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.remove_port_vlan(switch, port, vlan)
        except Exception as e:
            logger.error(f"Failed to remove VLAN: {e}")
            return False

    async def get_port_config(self, switch: str, port: str) -> Optional[dict]:
        """Get current port configuration"""
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return None

        try:
            return await self._default_plugin.get_port_config(switch, port)
        except Exception as e:
            logger.error(f"Failed to get port config: {e}")
            return None

    async def create_vlan(self, switch: str, vlan: int, name: str = "") -> bool:
        """Create a VLAN on the switch"""
        if not self._default_plugin:
            logger.error("No switch plugin enabled")
            return False

        logger.info(f"Creating VLAN {vlan} on {switch} via {self._default_plugin.name}")
        try:
            return await self._default_plugin.create_vlan(switch, vlan, name)
        except Exception as e:
            logger.error(f"Failed to create VLAN: {e}")
            return False


# Singleton instance
_dispatcher_instance: Optional[SwitchDispatcher] = None


def get_switch_dispatcher(plugin_manager: Optional[PluginManager] = None) -> SwitchDispatcher:
    """Get the global SwitchDispatcher instance"""
    global _dispatcher_instance

    if _dispatcher_instance is None:
        if plugin_manager is None:
            raise RuntimeError("PluginManager required to initialize SwitchDispatcher")
        _dispatcher_instance = SwitchDispatcher(plugin_manager)

    return _dispatcher_instance


# Convenience functions
async def set_port_vlan(switch: str, port: str, vlan: int, native: bool = False) -> bool:
    """
    Configure VLAN on a switch port.

    Example:
        from quads.plugins.switch_dispatcher import set_port_vlan

        # Works with any switch vendor (Juniper, Arista, Cisco, etc.)
        await set_port_vlan("switch01", "ge-0/0/1", 100)
    """
    dispatcher = get_switch_dispatcher()
    return await dispatcher.set_port_vlan(switch, port, vlan, native)


async def remove_port_vlan(switch: str, port: str, vlan: int) -> bool:
    """Remove VLAN from switch port"""
    dispatcher = get_switch_dispatcher()
    return await dispatcher.remove_port_vlan(switch, port, vlan)


async def create_vlan(switch: str, vlan: int, name: str = "") -> bool:
    """Create VLAN on switch"""
    dispatcher = get_switch_dispatcher()
    return await dispatcher.create_vlan(switch, vlan, name)
