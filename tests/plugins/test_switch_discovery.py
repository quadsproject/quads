"""Tests for switch-side host discovery (RFE #231)."""

import asyncio
import logging
import os

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

# QuadsCli import instantiates QuadsApi(Config) at import time, so config must
# resolve (conftest sets this under pytest; set it here too for standalone runs).
os.environ.setdefault("QUADS_CONF_DIR", str(Path(__file__).resolve().parents[2] / "conf"))

from quads.cli.cli import QuadsCli  # noqa: E402
from quads.plugins.builtin.switches.arista import AristaSwitchPlugin  # noqa: E402
from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin  # noqa: E402

# discover() routes through the shared base helper, so SSHHelper is patched there.
SSH_HELPER = "quads.plugins.interfaces.switch.SSHHelper"


LLDP_OUT = [
    "Local Interface    Parent Interface    Chassis Id          Port info     System Name\n",
    "xe-0/0/1           -                   00:11:22:33:44:55   em1           host01.example.com\n",
    "xe-0/0/2           -                   00:11:22:33:44:66   520           host02\n",
    "et-0/0/48          -                   aa:bb:cc:00:00:01   et-0/0/47     spine1\n",
]

FDB_OUT = [
    "Vlan name   MAC address        MAC flags   Logical interface\n",
    "default     00:aa:bb:cc:dd:01  D           xe-0/0/1.0\n",
    "default     00:aa:bb:cc:dd:02  D           xe-0/0/2.0\n",
    "trunkvl     00:aa:bb:cc:dd:03  D           et-0/0/48.0\n",
    "trunkvl     00:aa:bb:cc:dd:04  D           et-0/0/48.0\n",
]


def test_parse_lldp_neighbors():
    neighbors = JuniperSwitchPlugin._parse_lldp_neighbors(LLDP_OUT)
    assert set(neighbors) == {"xe-0/0/1", "xe-0/0/2", "et-0/0/48"}
    assert neighbors["xe-0/0/1"] == {"port_info": "em1", "system_name": "host01.example.com"}
    assert neighbors["et-0/0/48"]["system_name"] == "spine1"


def test_parse_fdb_strips_unit_and_groups_trunk():
    fdb = JuniperSwitchPlugin._parse_fdb(FDB_OUT)
    assert fdb["xe-0/0/1"] == ["00:aa:bb:cc:dd:01"]
    # logical unit (.0) stripped to the physical port QUADS stores
    assert "xe-0/0/1.0" not in fdb
    # a port with >1 learned MAC is an uplink/trunk
    assert fdb["et-0/0/48"] == ["00:aa:bb:cc:dd:03", "00:aa:bb:cc:dd:04"]


def test_parse_fdb_ignores_non_port_rows():
    assert JuniperSwitchPlugin._parse_fdb(["VLAN  MAC address  Type", "flood  -  all"]) == {}


def _plugin():
    with (
        patch("quads.plugins.builtin.switches.juniper.QuadsApi"),
        patch("quads.plugins.builtin.switches.juniper.Config"),
    ):
        plugin = JuniperSwitchPlugin(config={"enabled": True, "username": "admin"})
        plugin.logger = MagicMock()
        plugin.initialize()
        return plugin


def test_discover_joins_lldp_and_fdb():
    plugin = _plugin()
    ssh = MagicMock()
    ssh.run_cmd.side_effect = [(True, LLDP_OUT), (True, FDB_OUT)]
    with patch(SSH_HELPER, return_value=ssh):
        rows = asyncio.run(plugin.discover("10.0.0.1"))

    by_port = {row["switch_port"]: row for row in rows}
    assert len(rows) == 4  # one per learned MAC, trunk port contributes two
    assert by_port["xe-0/0/1"] == {
        "switch_ip": "10.0.0.1",
        "switch_port": "xe-0/0/1",
        "switch_vendor": "juniper",
        "mac_address": "00:aa:bb:cc:dd:01",
        "name": "em1",
        "neighbor": "host01.example.com",
        "trunk": False,
    }
    assert all(row["trunk"] for row in rows if row["switch_port"] == "et-0/0/48")
    ssh.disconnect.assert_called_once()


# ---- Arista (dotted MACs, Et ports, LLDP columns: Port | Device ID | Port ID | TTL)

ARISTA_LLDP_OUT = [
    "Last table change time   : 0:00:05 ago\n",
    "Number of table inserts  : 3\n",
    "\n",
    "Port       Neighbor Device ID      Neighbor Port ID    TTL\n",
    "Et1        host01.example.com      em1                 120\n",
    "Et2        host02                  520                 120\n",
    "Et48       spine1.example.com      Ethernet47          120\n",
]

ARISTA_FDB_OUT = [
    "          Mac Address Table\n",
    "----------------------------------------------------------\n",
    "Vlan    Mac Address       Type        Ports      Moves   Last Move\n",
    "----    -----------       ----        -----      -----   ---------\n",
    " 100    0011.2233.4401    DYNAMIC     Et1        1       0:00:05 ago\n",
    " 100    0011.2233.4402    DYNAMIC     Et2        1       0:00:05 ago\n",
    " 200    aabb.cc00.0001    DYNAMIC     Et48       1       0:00:05 ago\n",
    " 200    aabb.cc00.0002    DYNAMIC     Et48       1       0:00:05 ago\n",
    "Total Mac Addresses for this criterion: 4\n",
]


def test_arista_parse_lldp_neighbors_skips_summary_and_header():
    neighbors = AristaSwitchPlugin._parse_lldp_neighbors(ARISTA_LLDP_OUT)
    assert set(neighbors) == {"Et1", "Et2", "Et48"}
    assert neighbors["Et1"] == {"system_name": "host01.example.com", "port_info": "em1"}
    assert neighbors["Et48"]["port_info"] == "Ethernet47"


def test_arista_parse_fdb_normalizes_dotted_macs():
    fdb = AristaSwitchPlugin._parse_fdb(ARISTA_FDB_OUT)
    assert fdb["Et1"] == ["00:11:22:33:44:01"]
    # dotted -> colon, grouped; port with >1 MAC is a trunk/uplink
    assert fdb["Et48"] == ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"]


def _arista_plugin():
    with (
        patch("quads.plugins.builtin.switches.arista.QuadsApi"),
        patch("quads.plugins.builtin.switches.arista.Config"),
    ):
        plugin = AristaSwitchPlugin(config={"enabled": True, "username": "admin"})
        plugin.logger = MagicMock()
        plugin.initialize()
        return plugin


def test_arista_discover_joins_lldp_and_fdb():
    plugin = _arista_plugin()
    ssh = MagicMock()
    ssh.run_cmd.side_effect = [(True, ARISTA_LLDP_OUT), (True, ARISTA_FDB_OUT)]
    with patch(SSH_HELPER, return_value=ssh):
        rows = asyncio.run(plugin.discover("10.0.0.2"))

    by_port = {row["switch_port"]: row for row in rows}
    assert len(rows) == 4
    assert by_port["Et1"] == {
        "switch_ip": "10.0.0.2",
        "switch_port": "Et1",
        "switch_vendor": "arista",
        "mac_address": "00:11:22:33:44:01",
        "name": "em1",
        "neighbor": "host01.example.com",
        "trunk": False,
    }
    assert all(row["trunk"] for row in rows if row["switch_port"] == "Et48")


def test_arista_parse_fdb_skips_multicast_and_broadcast():
    # Real-shaped EOS output: a unicast host MAC on Et3, plus inline IPv4/IPv6
    # multicast and a trailing Multicast table. Only the host MAC should remain,
    # so Et3 is not wrongly flagged as a trunk.
    lines = [
        "Vlan    Mac Address       Type        Ports      Moves   Last Move\n",
        " 100    0c74.3988.0001    DYNAMIC     Et3        1       0:00:05 ago\n",
        " 100    0100.5e00.0001    STATIC      Et3\n",
        " 100    3333.0000.0001    STATIC      Et3\n",
        "          Multicast Mac Address Table\n",
        " 100    0100.5e7f.0002    STATIC      Et3 Et4\n",
    ]
    fdb = AristaSwitchPlugin._parse_fdb(lines)
    assert fdb == {"Et3": ["0c:74:39:88:00:01"]}


def _cli_with_existing(interfaces):
    quads = MagicMock()
    quads.get_host.return_value = SimpleNamespace(name="host01", interfaces=interfaces)
    cli = QuadsCli(quads=quads, logger=logging.getLogger("test-discovery"))
    return cli, quads


def test_apply_updates_matching_mac_and_creates_new():
    existing = [
        # same MAC (case-insensitive), switch_port moved -> update by id
        SimpleNamespace(
            id=11,
            name="em1",
            mac_address="00:AA:BB:CC:DD:01",
            switch_ip="10.0.0.1",
            switch_port="old-port",
            switch_vendor="juniper",
        ),
        # same MAC, identical location -> no write
        SimpleNamespace(
            id=12,
            name="em2",
            mac_address="00:aa:bb:cc:dd:02",
            switch_ip="10.0.0.1",
            switch_port="xe-0/0/2",
            switch_vendor="juniper",
        ),
    ]
    cli, quads = _cli_with_existing(existing)
    rows = [
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/1",
            "switch_vendor": "juniper",
            "mac_address": "00:aa:bb:cc:dd:01",
            "name": "em1",
            "neighbor": "host01",
            "trunk": False,
        },
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/2",
            "switch_vendor": "juniper",
            "mac_address": "00:aa:bb:cc:dd:02",
            "name": "em2",
            "neighbor": "host01",
            "trunk": False,
        },
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/3",
            "switch_vendor": "juniper",
            "mac_address": "00:aa:bb:cc:dd:03",
            "name": "em3",
            "neighbor": "host01",
            "trunk": False,
        },
    ]

    cli._apply_discovered("host01", rows)

    # existing MAC with a moved port -> update by id, only the changed field
    quads.update_interface.assert_called_once_with("host01", {"id": 11, "switch_port": "xe-0/0/1"})
    # new MAC -> create, stamped with the discovering plugin's vendor
    assert quads.create_interface.call_count == 1
    created = quads.create_interface.call_args.args[1]
    assert created["mac_address"] == "00:aa:bb:cc:dd:03"
    assert created["switch_port"] == "xe-0/0/3"
    assert created["switch_vendor"] == "juniper"


def test_apply_is_a_noop_when_nothing_changed():
    existing = [
        SimpleNamespace(
            id=1,
            name="em1",
            mac_address="00:aa:bb:cc:dd:01",
            switch_ip="10.0.0.1",
            switch_port="xe-0/0/1",
            switch_vendor="juniper",
        )
    ]
    cli, quads = _cli_with_existing(existing)
    rows = [
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/1",
            "switch_vendor": "juniper",
            "mac_address": "00:aa:bb:cc:dd:01",
            "name": "em1",
            "neighbor": "host01",
            "trunk": False,
        }
    ]

    cli._apply_discovered("host01", rows)

    quads.update_interface.assert_not_called()
    quads.create_interface.assert_not_called()


def test_apply_falls_back_to_nicn_when_lldp_port_id_is_a_mac():
    # A host without lldpd advertises a dotted MAC as its port-id; it must not
    # become the interface name.
    cli, quads = _cli_with_existing([])
    rows = [
        {
            "switch_ip": "10.0.0.2",
            "switch_port": "Et1",
            "switch_vendor": "arista",
            "mac_address": "70:72:cf:b7:68:72",
            "name": "7072.cfb7.6872",
            "neighbor": "host01",
            "trunk": False,
        }
    ]

    cli._apply_discovered("host01", rows)

    created = quads.create_interface.call_args.args[1]
    assert created["name"] == "nic1"
    assert created["switch_vendor"] == "arista"


if __name__ == "__main__":
    test_parse_lldp_neighbors()
    test_parse_fdb_strips_unit_and_groups_trunk()
    test_parse_fdb_ignores_non_port_rows()
    test_discover_joins_lldp_and_fdb()
    test_arista_parse_lldp_neighbors_skips_summary_and_header()
    test_arista_parse_fdb_normalizes_dotted_macs()
    test_arista_parse_fdb_skips_multicast_and_broadcast()
    test_arista_discover_joins_lldp_and_fdb()
    test_apply_updates_matching_mac_and_creates_new()
    test_apply_is_a_noop_when_nothing_changed()
    test_apply_falls_back_to_nicn_when_lldp_port_id_is_a_mac()
    print("ok")
