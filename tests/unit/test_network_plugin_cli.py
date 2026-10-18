"""Tests for the --network-plugin CLI action."""

import logging
from collections import Counter
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import quads.cli.cli as cli_module
from quads.cli import QuadsCli
from quads.cli.parser import parser
from quads.exceptions import CliException


def _cli():
    return QuadsCli(quads=MagicMock(), logger=logging.getLogger("test_network_plugin"))


def test_parser_requires_network_plugin_argument():
    with pytest.raises(SystemExit):
        parser.parse_args(["--network-plugin"])


def test_parser_accepts_comma_separated_drivers():
    args = parser.parse_args(["--network-plugin", "arista,juniper"])
    assert args.network_plugin == "arista,juniper"
    assert args.action is None


def test_parser_rejects_network_plugin_with_other_action():
    with pytest.raises(SystemExit):
        parser.parse_args(["--network-plugin", "juniper", "--verify-switch-conf"])


def test_action_rejects_driver_missing_for_defined_interface(monkeypatch):
    cli = _cli()
    cli.cli_args = {"network_plugin": "juniper"}
    update = MagicMock()
    monkeypatch.setattr(
        cli_module,
        "database_interface_vendor_counts",
        lambda: Counter({"juniper": 1, "arista": 1}),
    )
    monkeypatch.setattr(cli_module, "update_switch_driver_config", update)

    with pytest.raises(CliException) as exc:
        cli.action_network_plugin()

    assert "defined with type 'arista'" in str(exc.value)
    assert "driver is disabled" in str(exc.value)
    update.assert_not_called()


def test_action_updates_config_prints_and_restarts(monkeypatch, capsys):
    cli = _cli()
    cli.cli_args = {"network_plugin": "network"}
    update = MagicMock(return_value={"network": {"enabled": True}})
    restart = MagicMock()
    monkeypatch.setattr(cli_module, "database_interface_vendor_counts", lambda: Counter({"juniper": 1}))
    monkeypatch.setattr(cli_module, "update_switch_driver_config", update)
    monkeypatch.setattr(cli_module, "restart_quads_server", restart)

    assert cli.action_network_plugin() == 0

    out = capsys.readouterr().out
    assert "Enabled switch drivers: network" in out
    assert "Restarting quads-server..." in out
    assert "quads-server restarted." in out
    update.assert_called_once_with({"network"})
    restart.assert_called_once_with()


def test_action_reports_restart_failure_after_config_update(monkeypatch):
    cli = _cli()
    cli.cli_args = {"network_plugin": "juniper"}
    monkeypatch.setattr(cli_module, "database_interface_vendor_counts", lambda: Counter({"juniper": 1}))
    monkeypatch.setattr(cli_module, "update_switch_driver_config", MagicMock(return_value={}))

    def fail():
        raise CliException("failed to restart quads-server")

    monkeypatch.setattr(cli_module, "restart_quads_server", fail)

    with pytest.raises(CliException, match="configuration was updated, but failed to restart"):
        cli.action_network_plugin()


def test_run_dispatches_network_plugin(monkeypatch):
    cli = _cli()
    monkeypatch.setattr(cli, "action_network_plugin", MagicMock(return_value=0))

    assert cli.run(None, {"network_plugin": "network"}) == 0
    cli.action_network_plugin.assert_called_once_with()


def test_restart_quads_server_uses_systemctl(monkeypatch):
    run = MagicMock(return_value=SimpleNamespace(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(cli_module.subprocess, "run", run)

    cli_module.restart_quads_server()

    run.assert_called_once_with(
        ["systemctl", "restart", "quads-server"],
        capture_output=True,
        text=True,
        check=False,
    )


def test_restart_quads_server_reports_failure(monkeypatch):
    run = MagicMock(return_value=SimpleNamespace(returncode=1, stdout="", stderr="permission denied"))
    monkeypatch.setattr(cli_module.subprocess, "run", run)

    with pytest.raises(CliException, match="permission denied"):
        cli_module.restart_quads_server()
