"""Tests for the generic recipe-driven switch CLI runner."""

import logging

import pytest

from quads.tools.external.switch_cli import SwitchCLI, SwitchCLIException

JUNIPER_CFG = {
    "username": "scaleadmin",
    "connection": {
        "ssh": "ssh -o StrictHostKeyChecking=no {username}@{switch_ip}",
        "login_prompt": ">",
        "error_prefixes": ["error:"],
    },
    "operations": {
        "set_port_qinq": {
            "commands": [
                "edit",
                "rollback",
                "delete interfaces {switch_port}",
                "set interfaces {switch_port} apply-groups QinQ_vl{new_vlan}",
                {"cmd": "set interfaces {switch_port} speed {speed}g", "if": "speed"},
                {"cmd": "delete vlans vlan{old_vlan} interface {switch_port}", "if": "old_vlan"},
                "set vlans vlan{new_vlan} interface {switch_port}",
            ],
            "save": "commit",
            "save_wait": "commit complete",
        },
        "get_vlan_qinq": {
            "command": "show configuration vlans | display set | match {switch_port}.0",
            "parse": {"pattern": r"vlan(\d+) interface {switch_port}"},
        },
    },
}


def test_dry_run_set_operation_returns_true(caplog):
    """Dry-run should log the command sequence and not connect."""
    cli = SwitchCLI(JUNIPER_CFG, {"username": "scaleadmin", "switch_ip": "10.0.0.1", "switch_port": "et-0/0/0:0",
                                  "speed": 25, "speed_mbps": 25000, "old_vlan": 0, "new_vlan": 1110},
                    dry_run=True)
    with caplog.at_level(logging.INFO):
        result = cli.run(JUNIPER_CFG["operations"]["set_port_qinq"])
    assert result is True
    assert "SWITCH DRY-RUN: set interfaces et-0/0/0:0 apply-groups QinQ_vl1110" in caplog.text
    assert "speed 25g" in caplog.text
    # speed=25 is truthy, old_vlan=0 is falsy -> the delete command is skipped
    assert "delete vlans vlan0" not in caplog.text


def test_dry_run_skips_speed_when_zero(caplog):
    cli = SwitchCLI(JUNIPER_CFG, {"username": "scaleadmin", "switch_ip": "10.0.0.1", "switch_port": "et-0/0/0:0",
                                  "speed": 0, "speed_mbps": 0, "old_vlan": 1100, "new_vlan": 1110},
                    dry_run=True)
    with caplog.at_level(logging.INFO):
        assert cli.run(JUNIPER_CFG["operations"]["set_port_qinq"]) is True
    assert "speed 0g" not in caplog.text
    assert "delete vlans vlan1100" in caplog.text


def test_dry_run_save_list(caplog):
    """Save sequences that are lists (arista) are all sent."""
    cfg = {
        "username": "switch_username",
        "connection": {"ssh": "ssh {username}@{switch_ip}", "login_prompt": "#", "error_prefixes": ["%"]},
        "operations": {
            "set_port_qinq": {
                "commands": ["configure terminal"],
                "save": ["write memory", "copy running-configuration startup-configuration"],
                "save_wait": "Copy completed",
            }
        },
    }
    cli = SwitchCLI(cfg, {"username": "switch_username", "switch_ip": "10.0.0.2", "switch_port": "Et10/2"},
                    dry_run=True)
    with caplog.at_level(logging.INFO):
        assert cli.run(cfg["operations"]["set_port_qinq"]) is True
    assert "SWITCH DRY-RUN: write memory" in caplog.text
    assert "SWITCH DRY-RUN: copy running-configuration startup-configuration" in caplog.text


def test_missing_recipe_parameter_raises():
    cli = SwitchCLI(JUNIPER_CFG, {"username": "scaleadmin", "switch_ip": "10.0.0.1"}, dry_run=True)
    with pytest.raises(SwitchCLIException):
        cli.run(JUNIPER_CFG["operations"]["set_port_qinq"])
