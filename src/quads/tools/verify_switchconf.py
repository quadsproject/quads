#!/usr/bin/env python3

import argparse
import logging

from quads.config import Config, DEFAULT_CONF_PATH
from quads.helpers.utils import get_vlan
from quads.quads_api import QuadsApi
from quads.tools.external.juniper import Juniper
from quads.tools.external.ssh_helper import SSHHelper

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def verify(_cloud_name, _host_name, change=False):  # pragma: no cover
    Config.load_from_yaml(DEFAULT_CONF_PATH)

    quads = QuadsApi(config=Config)
    if not _cloud_name and not _host_name:
        logger.warning("At least one of --cloud or --host should be specified.")
        return

    _cloud_obj = None
    if _cloud_name:
        _cloud = quads.get_cloud(_cloud_name)
        if not _cloud:
            logger.error("Cloud not found.")
            return

    if _host_name:
        hosts = quads.filter_hosts({"name": _host_name, "retired": False})
        if not hosts:
            logger.error("Host not found.")
            return
    else:
        hosts = quads.filter_hosts({"cloud": _cloud_name, "retired": False})
        if not hosts:
            logger.error("No hosts found on cloud.")
            return
    first_host = hosts[0]

    if not _cloud_obj:
        _cloud_obj = first_host.cloud

    if _cloud_obj != first_host.cloud:
        logger.warning("Both --cloud and --host have been specified.")
        logger.warning(f"Host: {first_host.name}")
        logger.warning(f"Cloud: {_cloud_obj.name}")
        logger.warning(f"However, {first_host.name} is a member of {first_host.cloud.name}")
        logger.warning("!!!!! Be certain this is what you want to do. !!!!!")

    _assignment = quads.get_active_cloud_assignment(_cloud_obj.name)

    for _host_obj in hosts:
        logger.info(f"Host: {_host_obj.name}")
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
                        logger.warning(
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
                    logger.warning("Interface %s not using QinQ_vl%s", interface.switch_port, vlan)

                if int(vlan_member) != int(vlan):
                    if not last_nic:
                        logger.warning(
                            "Interface %s appears to be a member of VLAN %s, should be %s",
                            interface.switch_port,
                            vlan_member,
                            vlan,
                        )

                    if change:
                        if _assignment and _assignment.vlan and last_nic:
                            if int(_assignment.vlan.vlan_id) != int(old_vlan):

                                logger.info(f"Change requested for {interface.name}")
                                logger.info("Setting last interface to public vlan %s." % _assignment.vlan.vlan_id)

                                juniper = Juniper(
                                    interface.switch_ip,
                                    interface.switch_port,
                                    interface.speed,
                                    old_vlan,
                                    vlan,
                                )
                                success = juniper.convert_port_public()
                            else:
                                logger.info(f"No changes required for {interface.name}")
                                continue
                        else:
                            logger.info(f"Change requested for {interface.name}")
                            juniper = Juniper(
                                interface.switch_ip,
                                interface.switch_port,
                                interface.speed,
                                vlan_member,
                                vlan,
                            )
                            success = juniper.set_port()

                        if success:
                            logger.info("Successfully updated switch settings.")
                        else:
                            logger.error(f"There was something wrong updating switch for {interface.name}")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Verify switch configs for a cloud or host")
    parser.add_argument(
        "--cloud",
        dest="cloud",
        type=str,
        default=None,
        help="Cloud name to verify switch configuration for.",
    )
    parser.add_argument(
        "--host",
        dest="host",
        type=str,
        default=None,
        help="Host name to verify switch configuration for.",
    )
    parser.add_argument("--change", dest="change", action="store_true", help="Commit changes on switch.")

    args = parser.parse_args()
    verify(args.cloud, args.host, args.change)
