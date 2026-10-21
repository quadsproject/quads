"""Tests for Rich console configuration in the CLI and tools (issue #754)."""

from unittest.mock import MagicMock

import pytest

from quads.cli import QuadsCli
from quads.tools import conf_check, reports


class _Interface:
    name = "em5"
    bios_id = None
    mac_address = "04:32:01:ab:62:f1"
    switch_ip = "192.168.1.53"
    switch_port = "et-0/0/12:1"
    speed = 25
    vendor = ""
    pxe_boot = False
    maintenance = False


@pytest.mark.parametrize(
    "value, emoji",
    [
        ("04:32:01:ab:62:f1", "\U0001F18E"),
        ("04:32:01:cd:62:f1", "\U0001F4BF"),
    ],
)
def test_cli_console_does_not_substitute_emoji_shortcodes(value, emoji):
    cli = QuadsCli(quads=MagicMock(), logger=MagicMock())

    with cli.console.capture() as capture:
        cli.console.print(value)

    output = capture.get()
    assert emoji not in output
    assert value in output


def test_ls_interface_table_keeps_mac_intact():
    cli = QuadsCli(quads=MagicMock(), logger=MagicMock())
    cli.cli_args = {"host": "d36-h12-000-r660.example.com"}
    cli.quads.get_host_interface.return_value = [_Interface()]

    with cli.console.capture() as capture:
        cli.action_interface()

    output = capture.get()
    assert "\U0001F18E" not in output
    assert "04:32:01:ab:62:f1" in output


def test_reports_console_does_not_substitute_emoji_shortcodes():
    with reports.console.capture() as capture:
        reports.console.print("04:32:01:ab:62:f1")

    output = capture.get()
    assert "\U0001F18E" not in output
    assert "04:32:01:ab:62:f1" in output


def test_report_html_keeps_emoji_like_data_intact():
    html = reports._report_to_html(
        "Interfaces",
        ["Name", "Description"],
        [["em5", "rack :ab: maint"]],
    )

    assert "\U0001F18E" not in html
    assert "rack :ab: maint" in html


def test_conf_check_console_does_not_substitute_emoji_shortcodes(monkeypatch, capsys):
    result = conf_check.ConfCheckResult(
        findings=[
            conf_check.CheckFinding(
                file="quads.yml",
                check_type="test",
                severity="warning",
                key="description",
                message="bad value 04:32:01:ab:62:f1",
            )
        ],
        files_checked=1,
    )
    monkeypatch.setattr(conf_check, "run_conf_check", lambda: result)

    assert conf_check.main() == 1

    output = capsys.readouterr().out
    assert "\U0001F18E" not in output
    assert "04:32:01:ab:62:f1" in output
