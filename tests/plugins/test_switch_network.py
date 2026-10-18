"""Tests for the generic network driver plugin."""

from types import SimpleNamespace

import pytest

from quads.plugins.builtin.switches.network import NetworkSwitchPlugin
from quads.tools.external.switch_cli import SwitchCLIException


class FakeInterface(SimpleNamespace):
    def __init__(self, name="em1", switch_vendor="juniper", switch_ip="10.0.0.1", switch_port="et-0/0/0:0",
                 speed=25):
        super().__init__(name=name, switch_vendor=switch_vendor, switch_ip=switch_ip, switch_port=switch_port,
                         speed=speed)


def test_vendor_cfg_missing_vendor_raises():
    plugin = NetworkSwitchPlugin({"enabled": True})
    plugin.recipes = {"juniper": {"operations": {}}}
    with pytest.raises(SwitchCLIException):
        plugin._vendor_cfg("host1", FakeInterface(switch_vendor=None))


def test_vendor_cfg_unknown_vendor_raises():
    plugin = NetworkSwitchPlugin({"enabled": True})
    plugin.recipes = {"juniper": {"operations": {}}}
    with pytest.raises(SwitchCLIException):
        plugin._vendor_cfg("host1", FakeInterface(switch_vendor="cisco"))


def test_vendor_cfg_ok():
    plugin = NetworkSwitchPlugin({"enabled": True})
    plugin.recipes = {"juniper": {"username": "scaleadmin", "operations": {}}}
    cfg = plugin._vendor_cfg("host1", FakeInterface())
    assert cfg["username"] == "scaleadmin"


def test_params_speed_units():
    plugin = NetworkSwitchPlugin({"enabled": True})
    params = plugin._params(FakeInterface(speed=25), {"username": "scaleadmin"})
    assert params["speed"] == 25
    assert params["speed_mbps"] == 25000
