"""Tests for the generic network driver plugin."""

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quads.config import Config
from quads.plugins.builtin.switches import network as network_module
from quads.plugins.builtin.switches.network import NetworkSwitchPlugin
from quads.tools.external.switch_cli import SwitchCLIException


class FakeInterface(SimpleNamespace):
    def __init__(self, name="em1", switch_vendor="juniper", switch_ip="10.0.0.1", switch_port="et-0/0/0:0",
                 speed=25):
        super().__init__(name=name, switch_vendor=switch_vendor, switch_ip=switch_ip, switch_port=switch_port,
                         speed=speed)


def make_plugin(recipes=None):
    plugin = NetworkSwitchPlugin({"enabled": True})
    plugin.recipes = recipes or {"juniper": {"username": "scaleadmin", "operations": {}}}
    return plugin


def test_vendor_cfg_null_defaults_to_juniper(caplog):
    """Pre-upgrade interfaces have no switch_vendor: keep juniper behavior."""
    plugin = make_plugin()
    cfg = plugin._vendor_cfg("host1", FakeInterface(switch_vendor=None))
    assert cfg["username"] == "scaleadmin"
    assert "assuming historical 'juniper'" in caplog.text


def test_vendor_cfg_unknown_vendor_raises():
    plugin = make_plugin()
    with pytest.raises(SwitchCLIException):
        plugin._vendor_cfg("host1", FakeInterface(switch_vendor="cisco"))


def test_vendor_cfg_ok():
    cfg = make_plugin()._vendor_cfg("host1", FakeInterface())
    assert cfg["username"] == "scaleadmin"


def test_params_speed_units():
    params = make_plugin()._params(FakeInterface(speed=25), {"username": "scaleadmin"})
    assert params["speed"] == 25
    assert params["speed_mbps"] == 25000


def test_params_username_falls_back_to_plugins_yml(monkeypatch):
    monkeypatch.setattr(Config, "plugins", {"juniper": {"username": "scaleadmin"}})
    plugin = make_plugin()
    params = plugin._params(FakeInterface(), {"username": "switch_username"})
    assert params["username"] == "scaleadmin"


def test_set_op_non_qinq_uses_dot1q_tunnel(monkeypatch):
    """Non-qinq clouds still get tunnel mode: access would drop tags."""
    calls = []

    class FakeCLI:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, operation):
            calls.append(operation)
            return True

    monkeypatch.setattr(network_module, "SwitchCLI", FakeCLI)
    plugin = make_plugin()
    cfg = {"operations": {
        "set_port_qinq": {"commands": ["configure terminal"]},
        "set_port_public": {"commands": ["configure terminal"]},
    }}
    assert plugin._set_op("host1", FakeInterface(), cfg, 1100, 1110, qinq=False,
                          params={"_public": False, "old_vlan": 1100, "new_vlan": 1110},
                          dry_run=False) is True
    assert calls and calls[0] is cfg["operations"]["set_port_qinq"]


def test_set_op_missing_operation_raises():
    plugin = make_plugin()
    cfg = {"operations": {"set_port_qinq": {"commands": ["configure terminal"]}}}
    with pytest.raises(SwitchCLIException, match="set_port_public"):
        plugin._set_op("host1", FakeInterface(), cfg, 1100, 1110, qinq=False,
                       params={"_public": True, "old_vlan": 1100, "new_vlan": 1110},
                       dry_run=False)


def test_configure_preflights_before_any_write():
    plugin = make_plugin()
    bad = FakeInterface(name="em2", switch_vendor="cisco")
    host = SimpleNamespace(interfaces=[FakeInterface(name="em1"), bad])
    plugin.quads = Mock()
    plugin.quads.get_host.return_value = host
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(qinq=True, vlan=None)
    plugin._get_op = Mock(return_value=1100)
    plugin._set_op = Mock(return_value=True)

    assert asyncio.run(plugin.configure("host1", "cloud01", "cloud02")) is False
    plugin._set_op.assert_not_called()
    plugin._get_op.assert_not_called()


def test_modify_without_cloud_returns_false():
    plugin = make_plugin()
    host = SimpleNamespace(cloud=None, interfaces=[FakeInterface()])
    plugin.quads = Mock()
    plugin.quads.get_host.return_value = host

    assert asyncio.run(plugin.modify("host1", True, {0: 1110})) is False


def test_verify_dry_run_still_reads_real(monkeypatch):
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1", cloud=SimpleNamespace(name="cloud01"),
        interfaces=[FakeInterface()],
    )
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud01"), vlan=None, qinq=False
    )
    # get_vlan(cloud01, index 0, not public) = 1100: return a match so
    # verify reports success while we check it read for real.
    reads = Mock(return_value=1100)
    plugin._get_op = reads

    assert asyncio.run(plugin.verify(host="host1", dry_run=True)) is True
    # Reads must not be dry-run-suppressed: that would report VLAN 0s.
    assert reads.call_count == 1
    assert reads.call_args[0][-1] is False


def test_ls_config_missing_vendor_returns_false():
    plugin = make_plugin()
    host = SimpleNamespace(name="host1", interfaces=[FakeInterface(switch_vendor="arista")])
    plugin.quads = Mock()
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=None, qinq=False)
    plugin.quads.filter_hosts.return_value = [host]

    assert asyncio.run(plugin.ls_config("cloud01")) is False
