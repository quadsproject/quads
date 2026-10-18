"""Tests for the generic network driver plugin."""

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from quads.config import Config
from quads.plugins.builtin.switches import network as network_module
from quads.plugins.builtin.switches.network import NetworkSwitchPlugin
from quads.tools.external.switch_cli import SwitchCLIException


class FakeInterface(SimpleNamespace):
    def __init__(self, name="em1", switch_vendor="juniper", switch_ip="10.0.0.1", switch_port="et-0/0/0:0", speed=25):
        super().__init__(
            name=name, switch_vendor=switch_vendor, switch_ip=switch_ip, switch_port=switch_port, speed=speed
        )


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
    """EOS speed tokens are derived from the Gbps speed."""
    params = make_plugin()._params(FakeInterface(speed=25), {"username": "scaleadmin"})
    assert params["speed"] == 25
    assert params["speed_eos"] == "25gfull"
    assert params["speed_forced"] is True
    assert params["speed_auto"] is False
    assert params["speed_fec"] is False
    one_g = make_plugin()._params(FakeInterface(speed=1), {"username": "scaleadmin"})
    assert one_g["speed_eos"] == "1000full"
    # 100G must use 'speed auto 100g-2' + RS-FEC, never 'speed forced'.
    hundred_g = make_plugin()._params(FakeInterface(speed=100), {"username": "scaleadmin"})
    assert hundred_g["speed_eos"] == "100g-2"
    assert hundred_g["speed_auto"] is True
    assert hundred_g["speed_forced"] is False
    assert hundred_g["speed_fec"] is True
    # speed=0 -> no speed command at all.
    none = make_plugin()._params(FakeInterface(speed=0), {"username": "scaleadmin"})
    assert none["speed_forced"] is False
    assert none["speed_auto"] is False
    assert none["speed_fec"] is False


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
    cfg = {
        "operations": {
            "set_port_qinq": {"commands": ["configure terminal"]},
            "set_port_public": {"commands": ["configure terminal"]},
        }
    }
    assert (
        plugin._set_op(
            "host1",
            FakeInterface(),
            cfg,
            1100,
            1110,
            params={"_public": False, "old_vlan": 1100, "new_vlan": 1110},
            dry_run=False,
        )
        is True
    )
    assert calls and calls[0] is cfg["operations"]["set_port_qinq"]


def test_set_op_missing_operation_raises():
    plugin = make_plugin()
    cfg = {"operations": {"set_port_qinq": {"commands": ["configure terminal"]}}}
    with pytest.raises(SwitchCLIException, match="set_port_public"):
        plugin._set_op(
            "host1",
            FakeInterface(),
            cfg,
            1100,
            1110,
            params={"_public": True, "old_vlan": 1100, "new_vlan": 1110},
            dry_run=False,
        )


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


def test_verify_cloud_agrees_no_spurious_warning(caplog):
    """Cloud objects have no value equality; the guard must compare names
    so a cloud-only verify does not warn about a host/cloud mismatch."""
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1",
        cloud=SimpleNamespace(name="cloud01"),
        interfaces=[FakeInterface()],
    )
    plugin.quads = Mock()
    plugin.quads.get_cloud.return_value = SimpleNamespace(name="cloud01")
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud01"), vlan=None, qinq=False
    )
    plugin._get_op = Mock(return_value=(1100, ""))

    assert asyncio.run(plugin.verify(cloud="cloud01")) is True
    assert "Both --cloud and --host" not in caplog.text


def test_verify_host_cloud_mismatch_warns(caplog):
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1",
        cloud=SimpleNamespace(name="cloud02"),
        interfaces=[FakeInterface()],
    )
    plugin.quads = Mock()
    plugin.quads.get_cloud.return_value = SimpleNamespace(name="cloud01")
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud02"), vlan=None, qinq=False
    )
    # get_vlan(cloud02, 0) = 1110: match it so verify succeeds while the
    # requested-cloud (cloud01) vs host-cloud (cloud02) warning fires.
    plugin._get_op = Mock(return_value=(1110, ""))

    assert asyncio.run(plugin.verify(cloud="cloud01", host="host1")) is True
    assert "Both --cloud and --host" in caplog.text


def test_verify_host_without_cloud_returns_false():
    plugin = make_plugin()
    host = SimpleNamespace(name="host1", cloud=None, interfaces=[FakeInterface()])
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]

    assert asyncio.run(plugin.verify(host="host1")) is False


def test_verify_no_active_assignment_fails_closed():
    """A None assignment must fail closed: no fall-through to derived
    VLANs and no port rewrite on change=True (spare-pool/fresh-install)."""
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1",
        cloud=SimpleNamespace(name="cloud01"),
        interfaces=[FakeInterface()],
    )
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = None
    plugin._set_op = Mock(return_value=True)

    assert asyncio.run(plugin.verify(host="host1", change=True)) is False
    plugin._set_op.assert_not_called()


def test_verify_dry_run_still_reads_real(monkeypatch):
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1",
        cloud=SimpleNamespace(name="cloud01"),
        interfaces=[FakeInterface()],
    )
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud01"), vlan=None, qinq=False
    )
    # get_vlan(cloud01, index 0, not public) = 1100: return a match so
    # verify reports success while we check it read for real.
    reads = Mock(return_value=(1100, ""))
    plugin._get_op = reads

    assert asyncio.run(plugin.verify(host="host1", dry_run=True)) is True
    # Reads must not be dry-run-suppressed: that would report VLAN 0s.
    assert reads.call_count == 1
    assert reads.call_args[0][-1] is False
    assert reads.call_args.kwargs["return_output"] is True


def test_ls_config_missing_vendor_returns_false():
    plugin = make_plugin()
    host = SimpleNamespace(name="host1", interfaces=[FakeInterface(switch_vendor="arista")])
    plugin.quads = Mock()
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=None, qinq=False)
    plugin.quads.filter_hosts.return_value = [host]

    assert asyncio.run(plugin.ls_config("cloud01")) is False


def test_modify_match_without_change_logs_already_configured(caplog):
    plugin = make_plugin()
    host = SimpleNamespace(cloud=SimpleNamespace(name="cloud01"), interfaces=[FakeInterface()])
    plugin.quads = Mock()
    plugin.quads.get_host.return_value = host
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=None, qinq=False)
    plugin._get_op = Mock(return_value=1400)

    caplog.set_level(logging.INFO)
    assert asyncio.run(plugin.modify("host1", False, {0: 1400})) is True
    assert "Interface em1 (juniper: 10.0.0.1) is already configured for vlan1400" in caplog.text


def test_modify_continues_after_interface_failure():
    plugin = make_plugin()
    host = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud01"),
        interfaces=[FakeInterface(name="em1"), FakeInterface(name="em2")],
    )
    plugin.quads = Mock()
    plugin.quads.get_host.return_value = host
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=None, qinq=False)
    plugin._get_op = Mock(side_effect=[1100, 1101])
    plugin._set_op = Mock(side_effect=[False, True])

    assert asyncio.run(plugin.modify("host1", True, {0: 1400, 1: 1401})) is False
    assert plugin._set_op.call_count == 2


def test_modify_no_interfaces_returns_true(caplog):
    plugin = make_plugin()
    host = SimpleNamespace(cloud=SimpleNamespace(name="cloud01"), interfaces=[])
    plugin.quads = Mock()
    plugin.quads.get_host.return_value = host

    assert asyncio.run(plugin.modify("host1", False, {})) is True
    assert "The host host1 has no interfaces defined" in caplog.text


def test_set_op_success_logs_vendor_and_switch_ip(monkeypatch, caplog):
    class FakeCLI:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, operation):
            return True

    monkeypatch.setattr(network_module, "SwitchCLI", FakeCLI)
    plugin = make_plugin()
    interface = FakeInterface(switch_vendor="arista", switch_ip="10.1.40.73")
    operations = {"set_port_qinq": {}}

    caplog.set_level(logging.INFO)
    assert (
        plugin._set_op(
            "host1",
            interface,
            {"operations": operations},
            1100,
            1110,
            {"_public": False, "old_vlan": 1100, "new_vlan": 1110},
            False,
        )
        is True
    )
    assert "Successfully updated switch settings (arista: 10.1.40.73)" in caplog.text


def _verify_host(plugin, interface, read_result, assignment_vlan=None):
    host = SimpleNamespace(name="host1", cloud=SimpleNamespace(name="cloud01"), interfaces=[interface])
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=assignment_vlan, qinq=False)
    plugin._vendor_cfg = Mock(return_value={"username": "scaleadmin", "operations": {}})
    plugin._get_op = Mock(return_value=read_result)
    return plugin


def test_verify_arista_speed_fec_ok(monkeypatch):
    plugin = make_plugin()
    interface = FakeInterface(switch_vendor="arista", switch_ip="10.1.40.73", speed=100)
    _verify_host(
        plugin,
        interface,
        (1100, "interface Et7/1\n speed auto 100g-2\n error-correction encoding reed-solomon\n"),
    )
    monkeypatch.setattr(network_module, "get_vlan", lambda *args, **kwargs: 1100)

    assert asyncio.run(plugin.verify(host="host1")) is True


def test_verify_arista_speed_mismatch_fails(monkeypatch, caplog):
    plugin = make_plugin()
    interface = FakeInterface(switch_vendor="arista", switch_ip="10.1.40.73", speed=100)
    _verify_host(plugin, interface, (1100, "interface Et7/1\n speed forced 25gfull\n"))
    monkeypatch.setattr(network_module, "get_vlan", lambda *args, **kwargs: 1100)

    assert asyncio.run(plugin.verify(host="host1")) is False
    assert "speed/FEC does not match quads speed 100 Gbps" in caplog.text
    assert "(arista: 10.1.40.73)" in caplog.text


def test_verify_arista_speed_only_change_repairs(monkeypatch):
    plugin = make_plugin()
    interface = FakeInterface(switch_vendor="arista", switch_ip="10.1.40.73", speed=100)
    _verify_host(plugin, interface, (1100, "interface Et7/1\n speed forced 25gfull\n"))
    plugin._set_op = Mock(return_value=True)
    monkeypatch.setattr(network_module, "get_vlan", lambda *args, **kwargs: 1100)

    assert asyncio.run(plugin.verify(host="host1", change=True)) is True
    plugin._set_op.assert_called_once()


def test_verify_juniper_logs_speed_skip(monkeypatch, caplog):
    plugin = make_plugin()
    interface = FakeInterface(switch_vendor="juniper")
    _verify_host(plugin, interface, (1100, ""))
    monkeypatch.setattr(network_module, "get_vlan", lambda *args, **kwargs: 1100)

    caplog.set_level(logging.INFO)
    assert asyncio.run(plugin.verify(host="host1")) is True
    assert caplog.text.count("Skipping speed/FEC checks for juniper interfaces") == 1


def test_verify_vlan_mismatch_logged_once_per_interface(monkeypatch, caplog):
    plugin = make_plugin()
    host = SimpleNamespace(
        name="host1",
        cloud=SimpleNamespace(name="cloud01"),
        interfaces=[
            FakeInterface(name="em1", switch_ip="10.1.32.158", switch_port="et-0/0/0:0"),
            FakeInterface(name="em2", switch_ip="10.1.33.182", switch_port="et-0/0/0:3"),
        ],
    )
    plugin.quads = Mock()
    plugin.quads.filter_hosts.return_value = [host]
    plugin.quads.get_active_cloud_assignment.return_value = SimpleNamespace(vlan=None, qinq=True)
    plugin._vendor_cfg = Mock(return_value={"username": "scaleadmin", "operations": {}})
    plugin._get_op = Mock(return_value=(1100, ""))
    monkeypatch.setattr(network_module, "get_vlan", lambda *args, **kwargs: 1140)

    assert asyncio.run(plugin.verify(host="host1")) is False
    for ctx in ("juniper: 10.1.32.158", "juniper: 10.1.33.182"):
        assert caplog.text.count(f"({ctx}) appears to be a member of VLAN 1100, should be 1140") == 1
