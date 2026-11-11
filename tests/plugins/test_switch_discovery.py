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
from quads.plugins.builtin.switches.juniper import JuniperSwitchPlugin  # noqa: E402


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
    with patch("quads.plugins.builtin.switches.juniper.SSHHelper", return_value=ssh):
        rows = asyncio.run(plugin.discover("10.0.0.1"))

    by_port = {row["switch_port"]: row for row in rows}
    assert len(rows) == 4  # one per learned MAC, trunk port contributes two
    assert by_port["xe-0/0/1"] == {
        "switch_ip": "10.0.0.1",
        "switch_port": "xe-0/0/1",
        "mac_address": "00:aa:bb:cc:dd:01",
        "name": "em1",
        "neighbor": "host01.example.com",
        "trunk": False,
    }
    assert all(row["trunk"] for row in rows if row["switch_port"] == "et-0/0/48")
    ssh.disconnect.assert_called_once()


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
            "mac_address": "00:aa:bb:cc:dd:01",
            "name": "em1",
            "neighbor": "host01",
            "trunk": False,
        },
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/2",
            "mac_address": "00:aa:bb:cc:dd:02",
            "name": "em2",
            "neighbor": "host01",
            "trunk": False,
        },
        {
            "switch_ip": "10.0.0.1",
            "switch_port": "xe-0/0/3",
            "mac_address": "00:aa:bb:cc:dd:03",
            "name": "em3",
            "neighbor": "host01",
            "trunk": False,
        },
    ]

    cli._apply_discovered("host01", rows, "juniper")

    # existing MAC with a moved port -> update by id, only the changed field
    quads.update_interface.assert_called_once_with("host01", {"id": 11, "switch_port": "xe-0/0/1"})
    # new MAC -> create
    assert quads.create_interface.call_count == 1
    created = quads.create_interface.call_args.args[1]
    assert created["mac_address"] == "00:aa:bb:cc:dd:03"
    assert created["switch_port"] == "xe-0/0/3"


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
            "mac_address": "00:aa:bb:cc:dd:01",
            "name": "em1",
            "neighbor": "host01",
            "trunk": False,
        }
    ]

    cli._apply_discovered("host01", rows, "juniper")

    quads.update_interface.assert_not_called()
    quads.create_interface.assert_not_called()


if __name__ == "__main__":
    test_parse_lldp_neighbors()
    test_parse_fdb_strips_unit_and_groups_trunk()
    test_parse_fdb_ignores_non_port_rows()
    test_discover_joins_lldp_and_fdb()
    test_apply_updates_matching_mac_and_creates_new()
    test_apply_is_a_noop_when_nothing_changed()
    print("ok")
