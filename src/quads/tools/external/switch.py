import logging
import sys

from quads.config import DEFAULT_CONF_PATH, Config
from quads.helpers.utils import get_vlan
from quads.quads_api import QuadsApi
from quads.tools.external.juniper import Juniper
from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException

quads = QuadsApi(Config)

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logger.propagate = False
logging.basicConfig(level=logging.INFO, format="%(message)s")


class Switch:
    def __init__(self):
        self.logger = logger

    def configure(self, host: str, old_cloud: str, new_cloud: str):  # pragma: no cover
        _host_obj = quads.get_host(host)
        _old_ass_cloud_obj = quads.get_active_cloud_assignment(old_cloud)
        _new_ass_cloud_obj = quads.get_active_cloud_assignment(new_cloud)
        if not _host_obj.interfaces:
            self.logger.error("Host has no interfaces defined.")
            return False
        self.logger.debug("Connecting to switch on: %s" % _host_obj.interfaces[0].switch_ip)
        switch_ip = None
        ssh_helper = None
        interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
        for i, interface in enumerate(interfaces):
            last_nic = i == len(_host_obj.interfaces) - 1
            if not switch_ip:
                switch_ip = interface.switch_ip
                try:
                    ssh_helper = SSHHelper(switch_ip, Config["junos_username"])
                except SSHHelperException:
                    self.logger.error(f"Failed to connect to switch: {switch_ip}")
                    return False
            else:
                if switch_ip != interface.switch_ip:
                    ssh_helper.disconnect()
                    switch_ip = interface.switch_ip
                    ssh_helper = SSHHelper(switch_ip, Config["junos_username"])
            result, old_vlan_out = ssh_helper.run_cmd("show configuration interfaces %s" % interface.switch_port)
            old_vlan = None
            if result and old_vlan_out:
                old_vlan = old_vlan_out[0].split(";")[0].split()[1][7:]
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

                    juniper = Juniper(
                        interface.switch_ip,
                        interface.switch_port,
                        interface.speed,
                        old_vlan,
                        _new_ass_cloud_obj.vlan.vlan_id,
                    )
                    success = juniper.convert_port_public()

                    if success:
                        self.logger.info("Successfully updated switch settings.")
                    else:
                        self.logger.error(
                            "There was something wrong updating switch for %s:%s" % (host, interface.name)
                        )
                        if ssh_helper:
                            ssh_helper.disconnect()
                        return False
            else:
                if int(old_vlan) != int(new_vlan):
                    juniper = Juniper(interface.switch_ip, interface.switch_port, interface.speed, old_vlan, new_vlan)
                    success = juniper.set_port()

                    if success:
                        self.logger.info("Successfully updated switch settings.")
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

    def modify(self, host, change=False, nic1=None, nic2=None, nic3=None, nic4=None, nic5=None):  # pragma: no cover
        _nics = {"em1": nic1, "em2": nic2, "em3": nic3, "em4": nic4, "em5": nic5}
        _host_obj = quads.get_host(host)
        if not _host_obj:
            self.logger.error("Hostname not found.")
            return

        self.logger.info(f"Host: {_host_obj.name}")
        if _host_obj.interfaces:
            interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
            for i, interface in enumerate(interfaces):
                vlan = _nics.get(interface.name)
                if vlan:
                    ssh_helper = SSHHelper(interface.switch_ip, Config["junos_username"])

                    try:
                        _, old_vlan_out = ssh_helper.run_cmd(
                            "show configuration interfaces %s" % interface.switch_port
                        )
                        old_vlan = old_vlan_out[0].split(";")[0].split()[1]
                        if old_vlan.startswith("QinQ"):
                            old_vlan = old_vlan[7:]
                    except IndexError:
                        old_vlan = 0

                    try:
                        _, vlan_member_out = ssh_helper.run_cmd(
                            "show configuration vlans | display set | match %s.0" % interface.switch_port
                        )
                        vlan_member = vlan_member_out[0].split()[2][4:].strip(",")
                    except IndexError:
                        self.logger.warning(
                            "Could not determine the previous VLAN member for %s, switch %s, switch port %s "
                            % (
                                interface.name,
                                interface.switch_ip,
                                interface.switch_port,
                            )
                        )
                        vlan_member = 0

                    ssh_helper.disconnect()

                    if int(old_vlan) != int(vlan):
                        self.logger.warning("Interface %s not using QinQ_vl%s", interface.switch_port, vlan)

                    if int(vlan_member) != int(vlan):
                        self.logger.warning(
                            "Interface %s appears to be a member of VLAN %s, should be %s",
                            interface.switch_port,
                            vlan_member,
                            vlan,
                        )

                        if change:
                            self.logger.info(f"Change requested for {interface.name}")
                            juniper = Juniper(
                                interface.switch_ip,
                                interface.switch_port,
                                interface.speed,
                                vlan_member,
                                vlan,
                            )
                            success = juniper.set_port()

                            if success:
                                self.logger.info("Successfully updated switch settings.")
                            else:
                                self.logger.error(f"There was something wrong updating switch for {interface.name}")
                    else:
                        self.logger.info(f"Interface {interface.name} is already configured for vlan{vlan}")
        else:
            self.logger.error("The host has no interfaces defined")

    def verify(self, host=None, cloud=None, change=False):  # pragma: no cover
        Config.load_from_yaml(DEFAULT_CONF_PATH)

        quads = QuadsApi(config=Config)
        if not cloud and not host:
            self.logger.warning("At least one of --cloud or --host should be specified.")
            return

        _cloud_obj = None
        if cloud:
            _cloud = quads.get_cloud(cloud)
            if not _cloud:
                self.logger.error("Cloud not found.")
                return

        if host:
            hosts = quads.filter_hosts({"name": host, "retired": False})
            if not hosts:
                self.logger.error("Host not found.")
                return
        else:
            hosts = quads.filter_hosts({"cloud": cloud, "retired": False})
            if not hosts:
                self.logger.error("No hosts found on cloud.")
                return
        first_host = hosts[0]

        if not _cloud_obj:
            _cloud_obj = first_host.cloud

        if _cloud_obj != first_host.cloud:
            self.logger.warning("Both --cloud and --host have been specified.")
            self.logger.warning(f"Host: {first_host.name}")
            self.logger.warning(f"Cloud: {_cloud_obj.name}")
            self.logger.warning(f"However, {first_host.name} is a member of {first_host.cloud.name}")
            self.logger.warning("!!!!! Be certain this is what you want to do. !!!!!")

        _assignment = quads.get_active_cloud_assignment(_cloud_obj.name)

        for _host_obj in hosts:
            self.logger.info(f"Host: {_host_obj.name}")
            if _host_obj.interfaces:
                interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
                for i, interface in enumerate(interfaces):
                    ssh_helper = SSHHelper(interface.switch_ip, Config["junos_username"])
                    last_nic = i == len(_host_obj.interfaces) - 1
                    vlan = get_vlan(_assignment, i, last_nic)

                    try:
                        _, old_vlan_out = ssh_helper.run_cmd(f"show configuration interfaces {interface.switch_port}")
                        old_vlan = old_vlan_out[0].split(";")[0].split()[1]
                        if old_vlan.startswith("QinQ"):
                            old_vlan = old_vlan[7:]
                    except IndexError:
                        old_vlan = 0

                    try:
                        _, vlan_member_out = ssh_helper.run_cmd(
                            "show configuration vlans | display set | match %s.0" % interface.switch_port
                        )
                        vlan_member = vlan_member_out[0].split()[2][4:].strip(",")
                    except IndexError:
                        if not _assignment.vlan and not last_nic:
                            self.logger.warning(
                                "Could not determine the previous VLAN member for %s, switch %s, switch port %s "
                                % (
                                    interface.name,
                                    interface.switch_ip,
                                    interface.switch_port,
                                )
                            )
                        vlan_member = 0

                    ssh_helper.disconnect()

                    if int(old_vlan) != int(vlan):
                        self.logger.warning("Interface %s not using QinQ_vl%s", interface.switch_port, vlan)

                    if int(vlan_member) != int(vlan):
                        if not last_nic:
                            self.logger.warning(
                                "Interface %s appears to be a member of VLAN %s, should be %s",
                                interface.switch_port,
                                vlan_member,
                                vlan,
                            )

                        if change:
                            if _assignment and _assignment.vlan and last_nic:
                                if int(_assignment.vlan.vlan_id) != int(old_vlan):

                                    self.logger.info(f"Change requested for {interface.name}")
                                    self.logger.info(
                                        "Setting last interface to public vlan %s." % _assignment.vlan.vlan_id
                                    )

                                    juniper = Juniper(
                                        interface.switch_ip,
                                        interface.switch_port,
                                        interface.speed,
                                        old_vlan,
                                        vlan,
                                    )
                                    success = juniper.convert_port_public()
                                else:
                                    self.logger.info(f"No changes required for {interface.name}")
                                    continue
                            else:
                                self.logger.info(f"Change requested for {interface.name}")
                                juniper = Juniper(
                                    interface.switch_ip,
                                    interface.switch_port,
                                    interface.speed,
                                    vlan_member,
                                    vlan,
                                )
                                success = juniper.set_port()

                            if success:
                                self.logger.info("Successfully updated switch settings.")
                            else:
                                self.logger.error(f"There was something wrong updating switch for {interface.name}")

    def ls_config(self, cloud, all=False):
        _assignment = quads.get_active_cloud_assignment(cloud)

        if not _assignment:
            self.logger.error("Cloud not found.")
            return
        self.logger.info(f"Cloud qinq: {_assignment.qinq}")

        hosts = quads.filter_hosts({"cloud": cloud})
        if not all:
            hosts = [hosts[0]]

        for host in hosts:
            if all:
                self.logger.info(f"{host.name}:")
            if host and host.interfaces:
                interfaces = sorted(host.interfaces, key=lambda k: k.name)

                for i, interface in enumerate(interfaces):
                    ssh_helper = SSHHelper(interface.switch_ip, Config["junos_username"])
                    try:
                        if interface == interfaces[-1]:
                            _, vlan_member_out = ssh_helper.run_cmd(
                                f"show configuration interfaces {interface.switch_port}"
                            )
                            vlan_member = vlan_member_out[0].split(";")[0].split()[1]
                            if vlan_member.startswith("QinQ"):
                                vlan_member = vlan_member[7:]
                        else:
                            _, vlan_member_out = ssh_helper.run_cmd(
                                f"show configuration vlans | display set | match {interface.switch_port}.0"
                            )
                            vlan_member = vlan_member_out[0].split()[2][4:].strip(",")
                    except IndexError:
                        self.logger.warning(
                            "Could not determine the previous VLAN member for %s, switch %s, switch port %s "
                            % (
                                interface.name,
                                interface.switch_ip,
                                interface.switch_port,
                            )
                        )
                        vlan_member = 0

                    ssh_helper.disconnect()

                    self.logger.info(
                        f"Interface em{i + 1} appears to be a member of VLAN {vlan_member}",
                    )

            else:
                self.logger.error("The cloud has no hosts or the host has no interfaces defined")
