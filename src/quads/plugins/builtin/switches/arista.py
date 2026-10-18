from typing import Optional
from quads.helpers.utils import get_vlan
from quads.plugins.interfaces.switch import SwitchPlugin
from quads.config import DEFAULT_CONF_PATH, Config
from quads.quads_api import QuadsApi
from quads.tools.external.arista import Arista, expected_speed_statement, speed_statement_matches
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from quads.plugins.manager import PluginManager


class AristaSwitchPlugin(SwitchPlugin):
    """
    Arista switch plugin implementing SwitchPlugin interface.

    Manages switch configuration and management.
    """

    name = "arista"
    version = "1.0.0"
    description = "Arista switch plugin"
    author = "QUADS Team"

    def initialize(self, plugin_manager: Optional[PluginManager] = None):
        super().initialize(plugin_manager)
        self.quads = QuadsApi(Config)
        self.username = self.config.get("username")
        return True

    def _parse_vlan(self, output_lines):
        """Parse the current access (or trunk native) VLAN from interface output."""
        for line in output_lines or []:
            line = line.strip()
            if line.startswith("switchport access vlan") or line.startswith("switchport trunk native vlan"):
                return line.split()[-1]
        return None

    async def configure(self, host: str, old_cloud: str, new_cloud: str) -> bool:
        _host_obj = self.quads.get_host(host)
        _old_ass_cloud_obj = self.quads.get_active_cloud_assignment(old_cloud)
        _new_ass_cloud_obj = self.quads.get_active_cloud_assignment(new_cloud)
        if not _host_obj.interfaces:
            self.logger.error("Host has no interfaces defined.")
            return False
        interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
        unclaimed = self.unclaimed_interfaces(interfaces)
        if unclaimed:
            self.log_unclaimed(host, unclaimed)
            return False
        if not any(self.owns_interface(interface) for interface in interfaces):
            return True
        switch_ip = None
        ssh_helper = None
        for i, interface in enumerate(interfaces):
            if not self.owns_interface(interface):
                continue
            last_nic = i == len(interfaces) - 1
            if not switch_ip:
                switch_ip = interface.switch_ip
                try:
                    ssh_helper = SSHHelper(switch_ip, self.username)
                except SSHHelperException:
                    self.logger.error(f"Failed to connect to switch: {switch_ip}")
                    return False
            else:
                if switch_ip != interface.switch_ip:
                    ssh_helper.disconnect()
                    switch_ip = interface.switch_ip
                    ssh_helper = SSHHelper(switch_ip, self.username)
            result, old_vlan_out = ssh_helper.run_cmd("show running-config interfaces %s" % interface.switch_port)
            old_vlan = self._parse_vlan(old_vlan_out) if result else None
            if not old_vlan:
                if _new_ass_cloud_obj and not _new_ass_cloud_obj.vlan and not last_nic:
                    self.logger.warning(
                        "Warning: Could not determine the previous VLAN for %s on %s, switch %s, switchport %s"
                        % (
                            host,
                            interface.name,
                            interface.switch_ip,
                            interface.switch_port,
                        )
                    )
                old_vlan = get_vlan(_old_ass_cloud_obj, i, last_nic)

            new_vlan = get_vlan(_new_ass_cloud_obj, i, last_nic)

            if _new_ass_cloud_obj and _new_ass_cloud_obj.vlan and last_nic:
                if int(old_vlan) != int(_new_ass_cloud_obj.vlan.vlan_id):
                    self.logger.info("Setting last interface to public vlan %s." % new_vlan)

                    arista = Arista(
                        interface.switch_ip,
                        interface.switch_port,
                        interface.speed,
                        old_vlan,
                        _new_ass_cloud_obj.vlan.vlan_id,
                        self.username,
                    )
                    success = arista.convert_port_public()

                    if success:
                        self.logger.info(f"Successfully updated switch settings ({self.name}: {interface.switch_ip})")
                    else:
                        self.logger.error(
                            "There was something wrong updating switch for %s:%s" % (host, interface.name)
                        )
                        if ssh_helper:
                            ssh_helper.disconnect()
                        return False
            else:
                if int(old_vlan) != int(new_vlan):
                    arista = Arista(
                        interface.switch_ip,
                        interface.switch_port,
                        interface.speed,
                        old_vlan,
                        new_vlan,
                        self.username,
                    )
                    success = arista.set_port()

                    if success:
                        self.logger.info(f"Successfully updated switch settings ({self.name}: {interface.switch_ip})")
                    else:
                        self.logger.error(
                            "There was something wrong updating switch for %s:%s" % (host, interface.name)
                        )
                        if ssh_helper:
                            ssh_helper.disconnect()
                        return False

        if ssh_helper:
            ssh_helper.disconnect()

        return True

    async def modify(self, host, change=False, overrides=None):
        overrides = overrides or {}
        _host_obj = self.quads.get_host(host)
        if not _host_obj:
            self.logger.error("Hostname not found.")
            return False

        self.logger.info(f"Host: {_host_obj.name}")
        all_ok = True
        if _host_obj.interfaces:
            interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
            unclaimed = self.unclaimed_interfaces(interfaces)
            if unclaimed:
                self.log_unclaimed(_host_obj.name, unclaimed)
                return False
            for index in sorted(overrides.keys()):
                if index >= len(interfaces):
                    self.logger.warning(
                        "NIC index %d exceeds host interface count (%d), skipping",
                        index + 1,
                        len(interfaces),
                    )
            for i, interface in enumerate(interfaces):
                if not self.owns_interface(interface):
                    continue
                vlan = overrides.get(i)
                if vlan:
                    ssh_helper = SSHHelper(interface.switch_ip, self.username)

                    try:
                        _, old_vlan_out = ssh_helper.run_cmd(
                            "show running-config interfaces %s" % interface.switch_port
                        )
                        old_vlan = self._parse_vlan(old_vlan_out) or 0
                    except (IndexError, TypeError):
                        old_vlan = 0

                    ssh_helper.disconnect()

                    # On Arista, the interface access VLAN IS the membership.
                    if int(old_vlan) != int(vlan):
                        self.logger.warning(
                            "Interface %s appears to be a member of VLAN %s, should be %s",
                            interface.switch_port,
                            old_vlan,
                            vlan,
                        )

                        if change:
                            self.logger.info(f"Change requested for {interface.name}")
                            arista = Arista(
                                interface.switch_ip,
                                interface.switch_port,
                                interface.speed,
                                old_vlan,
                                vlan,
                                self.username,
                            )
                            success = arista.set_port()

                            if success:
                                self.logger.info(
                                    f"Successfully updated switch settings ({self.name}: {interface.switch_ip})"
                                )
                            else:
                                self.logger.error(f"There was something wrong updating switch for {interface.name}")
                                all_ok = False
                    else:
                        self.logger.info(f"Interface {interface.name} is already configured for vlan{vlan}")
        else:
            self.logger.error("The host has no interfaces defined")
        return all_ok

    async def verify(self, host=None, cloud=None, change=False):
        Config.load_from_yaml(DEFAULT_CONF_PATH)

        all_ok = True

        if not cloud and not host:
            self.logger.warning("At least one of --cloud or --host should be specified.")
            return False

        _cloud = None
        if cloud:
            _cloud = self.quads.get_cloud(cloud)
            if not _cloud:
                self.logger.error("Cloud not found.")
                return False

        if host:
            hosts = self.quads.filter_hosts({"name": host, "retired": False})
            if not hosts:
                self.logger.error("Host not found.")
                return False
        else:
            hosts = self.quads.filter_hosts({"cloud": cloud, "retired": False})
            if not hosts:
                self.logger.error("No hosts found on cloud.")
                return False
        first_host = hosts[0]

        if _cloud and _cloud.name != first_host.cloud.name:
            self.logger.warning("Both --cloud and --host have been specified.")
            self.logger.warning(f"Host: {first_host.name}")
            self.logger.warning(f"Cloud: {_cloud.name}")
            self.logger.warning(f"However, {first_host.name} is a member of {first_host.cloud.name}")
            self.logger.warning(f"!!!!! {_cloud.name} is ignored, verifying {first_host.cloud.name}. !!!!!")

        _assignment = self.quads.get_active_cloud_assignment(first_host.cloud.name)

        if not _assignment:
            self.logger.warning(
                "No active assignment for cloud %s, cannot verify switch configuration." % first_host.cloud.name
            )
            return False

        for _host_obj in hosts:
            self.logger.info(f"Host: {_host_obj.name}")
            if _host_obj.interfaces:
                interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
                unclaimed = self.unclaimed_interfaces(interfaces)
                if unclaimed:
                    self.log_unclaimed(_host_obj.name, unclaimed)
                    all_ok = False
                    continue
                for i, interface in enumerate(interfaces):
                    if not self.owns_interface(interface):
                        continue
                    ssh_helper = SSHHelper(interface.switch_ip, self.username)
                    last_nic = i == len(interfaces) - 1
                    vlan = get_vlan(_assignment, i, last_nic)

                    try:
                        _, old_vlan_out = ssh_helper.run_cmd(f"show running-config interfaces {interface.switch_port}")
                        old_vlan = self._parse_vlan(old_vlan_out) or 0
                    except (IndexError, TypeError):
                        old_vlan_out = []
                        old_vlan = 0

                    # On Arista, the interface access VLAN IS the membership.
                    vlan_member = old_vlan

                    ssh_helper.disconnect()

                    # VLAN-only verification masked a failed speed/save step:
                    # check the speed (and its 100G-only RS-FEC) too.
                    speed_ok = True
                    statement = expected_speed_statement(interface.speed)
                    if statement:
                        lines = [line.strip() for line in old_vlan_out or []]
                        has_fec = any("error-correction encoding reed-solomon" in line for line in lines)
                        is_100g = int(interface.speed) == 100
                        speed_ok = speed_statement_matches(statement, lines) and (has_fec if is_100g else not has_fec)
                        if not speed_ok:
                            self.logger.warning(
                                "Interface %s (%s: %s) speed/FEC does not match quads speed %s Gbps",
                                interface.switch_port,
                                self.name,
                                interface.switch_ip,
                                interface.speed,
                            )
                    if int(vlan_member) != int(vlan) or not speed_ok:
                        if change:
                            if _assignment and _assignment.vlan and last_nic:
                                if int(_assignment.vlan.vlan_id) != int(old_vlan) or not speed_ok:

                                    self.logger.info(f"Change requested for {interface.name}")
                                    self.logger.info(
                                        "Setting last interface to public vlan %s." % _assignment.vlan.vlan_id
                                    )

                                    arista = Arista(
                                        interface.switch_ip,
                                        interface.switch_port,
                                        interface.speed,
                                        old_vlan,
                                        vlan,
                                        self.username,
                                    )
                                    success = arista.convert_port_public()
                                else:
                                    self.logger.info(f"No changes required for {interface.name}")
                                    continue
                            else:
                                self.logger.info(f"Change requested for {interface.name}")
                                arista = Arista(
                                    interface.switch_ip,
                                    interface.switch_port,
                                    interface.speed,
                                    vlan_member,
                                    vlan,
                                    self.username,
                                )
                                success = arista.set_port()

                            if success:
                                self.logger.info(
                                    f"Successfully updated switch settings ({self.name}: {interface.switch_ip})"
                                )
                            else:
                                self.logger.error(f"There was something wrong updating switch for {interface.name}")
                                all_ok = False
                        else:
                            if int(vlan_member) != int(vlan):
                                self.logger.error(
                                    f"Interface {interface.switch_port} ({self.name}: {interface.switch_ip}) "
                                    f"appears to be a member of VLAN {vlan_member}, should be {vlan}"
                                )
                            all_ok = False
            else:
                self.logger.error(f"Host {_host_obj.name} has no interfaces defined.")
                all_ok = False

        return all_ok

    async def ls_config(self, cloud, all=False):
        _assignment = self.quads.get_active_cloud_assignment(cloud)

        if not _assignment:
            self.logger.error("Cloud not found.")
            return False
        self.logger.info(f"Cloud qinq: {_assignment.qinq}")

        hosts = self.quads.filter_hosts({"cloud": cloud})
        if not hosts:
            self.logger.error("No hosts found on cloud.")
            return False
        if not all:
            hosts = [hosts[0]]

        for host in hosts:
            if all:
                self.logger.info(f"{host.name}:")
            if host and host.interfaces:
                interfaces = sorted(host.interfaces, key=lambda k: k.name)
                for i, interface in enumerate(interfaces):
                    if not self.owns_interface(interface):
                        continue
                    ssh_helper = SSHHelper(interface.switch_ip, self.username)
                    try:
                        _, vlan_out = ssh_helper.run_cmd(f"show running-config interfaces {interface.switch_port}")
                        vlan_member = self._parse_vlan(vlan_out)
                        if vlan_member is None:
                            raise ValueError
                    except (IndexError, TypeError, ValueError):
                        self.logger.warning(
                            "Could not determine the previous VLAN member for %s, switch %s, switch port %s"
                            % (interface.name, interface.switch_ip, interface.switch_port)
                        )
                        vlan_member = 0

                    ssh_helper.disconnect()

                    self.logger.info(
                        f"Interface {interface.name} appears to be a member of VLAN {vlan_member}",
                    )

            else:
                self.logger.error("The cloud has no hosts or the host has no interfaces defined")
        return True
