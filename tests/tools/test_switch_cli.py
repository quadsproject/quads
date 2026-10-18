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


FAKE_SSH = "python3 tests/tools/fake_switch.py"


def _fake_cfg(**op_overrides):
    """A juniper-style recipe talking to the fake console."""
    conn = {
        "ssh": FAKE_SSH,
        "login_prompt": ">",
        "error_prefixes": ["error:", "%"],
        "timeout": 5,
    }
    operations = {
        "set_port_qinq": {
            "config_prompt": "#",
            "commands": ["edit", "rollback", "set vlans vlan{new_vlan} interface {switch_port}"],
            "save": "commit",
            "save_wait": "commit complete",
        },
        "set_port_public": {
            "config_prompt": "#",
            "commands": ["edit", "set interfaces {switch_port} native-vlan-id {new_vlan}"],
            "save": "commit",
            "save_wait": "commit complete",
        },
        "get_vlan_qinq": {
            "command": "show configuration vlans | display set | match {switch_port}.0 | no-more",
            "parse": {"pattern": r"vlan(\d+) interface {switch_port}"},
        },
        "get_vlan_public": {
            "command": "show configuration interfaces {switch_port} | no-more",
            "parse": {"pattern": r"native-vlan-id (\d+)"},
        },
    }
    for name, op in op_overrides.items():
        operations[name] = op
    return {"username": "scaleadmin", "connection": conn, "operations": operations}


def _params(**kw):
    base = {"username": "scaleadmin", "switch_ip": "10.0.0.1", "switch_port": "et-0/0/0:0",
            "speed": 25, "speed_mbps": 25000, "old_vlan": 1100, "new_vlan": 1110}
    base.update(kw)
    return base


def test_juniper_set_with_config_prompt_succeeds():
    """Regression: after 'edit' Junos prompts with '#', not '>'."""
    cfg = _fake_cfg()
    cli = SwitchCLI(cfg, _params())
    assert cli.run(cfg["operations"]["set_port_qinq"]) is True


def test_juniper_set_without_config_prompt_times_out():
    """The config-mode prompt must be declared or the set times out."""
    cfg = _fake_cfg()
    del cfg["operations"]["set_port_qinq"]["config_prompt"]
    cli = SwitchCLI(cfg, _params())
    with pytest.raises(SwitchCLIException):
        cli.run(cfg["operations"]["set_port_qinq"])


def test_get_parses_fake_output():
    cfg = _fake_cfg()
    cli = SwitchCLI(cfg, _params())
    assert cli.run(cfg["operations"]["get_vlan_qinq"]) == 1110


def test_arista_save_list_runs_both_saves():
    cfg = {
        "username": "scaleadmin",
        "connection": {"ssh": FAKE_SSH + " --enable", "login_prompt": "#", "error_prefixes": ["%"], "timeout": 5},
        "operations": {
            "set_port_qinq": {
                "commands": ["configure terminal", "interface {switch_port}"],
                "save": ["write memory", "copy running-config startup-config"],
                "save_wait": "Copy completed",
            }
        },
    }
    cli = SwitchCLI(cfg, _params(switch_port="Et10/2"))
    assert cli.run(cfg["operations"]["set_port_qinq"]) is True


def test_denied_copy_save_fails_fast_with_error():
    """A denied final save must surface the '%' error, not burn a timeout."""
    cfg = {
        "username": "scaleadmin",
        "connection": {"ssh": FAKE_SSH + " --enable --deny-copy", "login_prompt": "#",
                       "error_prefixes": ["%"], "timeout": 5},
        "operations": {
            "set_port_qinq": {
                "commands": ["configure terminal", "interface {switch_port}"],
                "save": ["write memory", "copy running-config startup-config"],
                "save_wait": "Copy completed",
            }
        },
    }
    cli = SwitchCLI(cfg, _params(switch_port="Et10/2"))
    with pytest.raises(SwitchCLIException, match="Authorization denied"):
        cli.run(cfg["operations"]["set_port_qinq"])


def test_switch_error_output_raises():
    cfg = _fake_cfg()
    cfg["operations"]["bogus"] = {"commands": ["default interface {switch_port}"]}
    cli = SwitchCLI(cfg, _params())
    with pytest.raises(SwitchCLIException, match="Authorization denied"):
        cli.run(cfg["operations"]["bogus"])


def test_validate_rejects_bad_recipe():
    with pytest.raises(SwitchCLIException, match="login_prompt"):
        SwitchCLI({"connection": {"ssh": "ssh x"}, "operations": {}}, {}).validate()
    bad = {
        "connection": {"ssh": "ssh x", "login_prompt": ">"},
        "operations": {"empty": {"command": "show", "commands": []}},
    }
    with pytest.raises(SwitchCLIException, match="exactly one"):
        SwitchCLI(bad, {}).validate()


def test_render_preserves_regex_quantifiers():
    cfg = _fake_cfg()
    # Single-number quantifier: {4} must not be mistaken for a placeholder.
    cfg["operations"]["get_vlan_qinq"]["parse"]["pattern"] = r"vlan(\d{4}) interface {switch_port}"
    cli = SwitchCLI(cfg, _params())
    assert cli.run(cfg["operations"]["get_vlan_qinq"]) == 1110
