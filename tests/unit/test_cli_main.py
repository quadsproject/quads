"""Tests for the CLI entry point's log stream and exit-code handling."""

import json
import sys
from types import SimpleNamespace

import pytest

import quads.cli.main as main_module
from quads.config import Config


class _FakeApi:
    def __init__(self, config=None):
        pass

    def get_host(self, hostname):
        return SimpleNamespace()

    def get_host_interface(self, hostname):
        return [
            SimpleNamespace(
                name="em1",
                bios_id=None,
                mac_address="04:32:01:ab:62:f1",
                switch_ip="192.168.241.253",
                switch_port="et-0/0/12:1",
                switch_vendor=None,
                speed=25,
                vendor=None,
                pxe_boot=False,
                maintenance=False,
            )
        ]


@pytest.fixture(autouse=True)
def fake_cli(monkeypatch):
    monkeypatch.setattr(main_module, "QuadsApi", _FakeApi)
    monkeypatch.setattr(Config, "load_from_yaml", lambda self, filepath=None: None)
    main_module.logger.handlers.clear()
    yield
    main_module.logger.handlers.clear()


def _run(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["quads", *argv])
    return main_module.main()


def test_json_logs_only_to_stderr(monkeypatch, capsys):
    assert _run(monkeypatch, "--json", "--debug", "--ls-interface", "--host", "host1") == 0

    out, err = capsys.readouterr()
    assert [row["name"] for row in json.loads(out)] == ["em1"]
    assert "Action: interface" in err
    assert "Action: interface" not in out


def test_json_requires_an_action(monkeypatch, capsys):
    assert _run(monkeypatch, "--json") == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert "requires one of the supported actions" in err


def test_json_rejects_unsupported_action(monkeypatch, capsys):
    assert _run(monkeypatch, "--json", "--version") == 2

    out, err = capsys.readouterr()
    assert out == ""
    assert "--json is not supported for this action" in err


def test_repeated_invocations_do_not_duplicate_log_handlers(monkeypatch, capsys):
    assert _run(monkeypatch, "--json", "--debug", "--ls-interface", "--host", "host1") == 0
    capsys.readouterr()

    assert _run(monkeypatch, "--json", "--debug", "--ls-interface", "--host", "host1") == 0

    out, err = capsys.readouterr()
    assert json.loads(out)
    assert err.count("Action: interface") == 1
