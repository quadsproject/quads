from typing import Optional

from quads.plugins.base import BasePlugin
from quads.plugins.manager import PluginManager
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from abc import abstractmethod


class SwitchPlugin(BasePlugin):
    """Interface for switch plugins.

    Action methods must return True on success; any other return value
    (False, None, ...) is treated as failure by the dispatcher.
    """

    # Interfaces with no switch_vendor belong to the plugin that declares
    # this True (the historical default), so only one plugin ever programs them.
    _owns_legacy_interfaces = False

    # Set by initialize() from PluginManager.load_plugin; None in bare unit tests.
    plugin_manager: Optional[PluginManager] = None

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        self.plugin_manager = plugin_manager
        return True

    def owns_interface(self, interface) -> bool:
        """True if this plugin is responsible for the interface."""
        vendor = getattr(interface, "switch_vendor", None)
        return vendor == self.name or (vendor is None and self._owns_legacy_interfaces)

    def unclaimed_interfaces(self, interfaces) -> list:
        """Interfaces that no enabled switch plugin owns, e.g. a typo'd or disabled switch_vendor."""
        if not self.plugin_manager:
            return []
        plugins = self.plugin_manager.get_plugins_by_type(SwitchPlugin)
        return [interface for interface in interfaces if not any(p.owns_interface(interface) for p in plugins)]

    def log_unclaimed(self, host: str, interfaces) -> None:
        self.logger.error(
            "No enabled switch plugin claims %s on %s (switch_vendor: %s), those switch ports were left untouched",
            ", ".join(interface.name for interface in interfaces),
            host,
            ", ".join(sorted({str(interface.switch_vendor) for interface in interfaces})),
        )

    async def discover(self, switch_ip: str) -> list:
        """
        Discover host NIC MACs and the switch ports they are learned on.

        Returns a list of dicts, one per learned MAC, with keys:
        switch_ip, switch_port, mac_address, name (suggested interface name /
        LLDP remote port-id, may be None), neighbor (LLDP system-name, may be
        None), trunk (True when the port learned more than one MAC).

        Non-abstract on purpose: vendors without discovery support and external
        plugins inherit this no-op instead of being forced to implement it.
        """
        self.logger.warning("Host discovery is not implemented for the %s switch plugin", self.name)
        return []

    async def _discover_from_tables(self, switch_ip: str, lldp_command: str, fdb_command: str) -> list:
        """Shared discovery skeleton for switches that expose LLDP neighbor and
        MAC-address tables over SSH.

        Vendors supply their own ``lldp_command``/``fdb_command`` and the
        ``_parse_lldp_neighbors``/``_parse_fdb`` parsers for their CLI output;
        the SSH handling and the join into per-MAC rows live here so they do not
        drift between vendors.
        """
        try:
            ssh_helper = SSHHelper(switch_ip, self.username)
        except SSHHelperException:
            self.logger.error(f"Failed to connect to switch: {switch_ip}")
            return []
        try:
            lldp_ok, lldp_out = ssh_helper.run_cmd(lldp_command)
            fdb_ok, fdb_out = ssh_helper.run_cmd(fdb_command)
        finally:
            ssh_helper.disconnect()

        neighbors = self._parse_lldp_neighbors(lldp_out if lldp_ok else [])
        fdb = self._parse_fdb(fdb_out if fdb_ok else [])

        rows = []
        for port in sorted(fdb):
            macs = fdb[port]
            neighbor = neighbors.get(port, {})
            for mac in macs:
                rows.append(
                    {
                        "switch_ip": switch_ip,
                        "switch_port": port,
                        "mac_address": mac,
                        "name": neighbor.get("port_info"),
                        "neighbor": neighbor.get("system_name"),
                        "trunk": len(macs) > 1,
                    }
                )
        return rows

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
