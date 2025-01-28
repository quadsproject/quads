#!/usr/bin/env python3

import argparse
import logging

from quads.config import Config
from quads.tools.external.juniper import Juniper
from quads.tools.external.ssh_helper import SSHHelper
from quads.quads_api import QuadsApi

quads = QuadsApi(Config)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")


def verify(_host_name, change=False, nic1=None, nic2=None, nic3=None, nic4=None, nic5=None):  # pragma: no cover
    _nics = {"em1": nic1, "em2": nic2, "em3": nic3, "em4": nic4, "em5": nic5}
    _host_obj = quads.get_host(_host_name)
    if not _host_obj:
        logger.error("Hostname not found.")
        return

    logger.info(f"Host: {_host_obj.name}")
    if _host_obj.interfaces:
        interfaces = sorted(_host_obj.interfaces, key=lambda k: k.name)
        for i, interface in enumerate(interfaces):
            vlan = _nics.get(interface.name)
            if vlan:
                ssh_helper = SSHHelper(interface.switch_ip, Config["junos_username"])

                try:
                    _, old_vlan_out = ssh_helper.run_cmd("show configuration interfaces %s" % interface.switch_port)
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
                    logger.warning(
                        "Interface %s appears to be a member of VLAN %s, should be %s",
                        interface.switch_port,
                        vlan_member,
                        vlan,
                    )

                    if change:
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
                else:
                    logger.info(f"Interface {interface.name} is already configured for vlan{vlan}")
    else:
        logger.error("The host has no interfaces defined")


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(description="Verify switch configs for a cloud or host")
    parser.add_argument(
        "--host",
        dest="host",
        type=str,
        default=None,
        help="Host name to verify switch configuration for.",
        required=True,
    )
    parser.add_argument(
        "--nic1",
        dest="nic1",
        type=str,
        default=None,
        help="Nic 1 (EM1).",
    )
    parser.add_argument(
        "--nic2",
        dest="nic2",
        type=str,
        default=None,
        help="Nic 2 (EM2).",
    )
    parser.add_argument(
        "--nic3",
        dest="nic3",
        type=str,
        default=None,
        help="Nic 3 (EM3).",
    )
    parser.add_argument(
        "--nic4",
        dest="nic4",
        type=str,
        default=None,
        help="Nic 4 (EM4).",
    )
    parser.add_argument(
        "--nic5",
        dest="nic5",
        type=str,
        default=None,
        help="Nic 5 (EM5).",
    )
    parser.add_argument("--change", dest="change", action="store_true", help="Commit changes on switch.")

    args = parser.parse_args()
    verify(args.host, args.change, args.nic1, args.nic2, args.nic3, args.nic4, args.nic5)
