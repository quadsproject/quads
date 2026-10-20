"""Tests for --json output of the table-producing CLI actions (issue #755)."""

import inspect
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from quads.cli import QuadsCli
from quads.exceptions import CliException
from quads.helpers.utils import time_remaining
from quads.server.models import Schedule


def _make_cli():
    return QuadsCli(quads=MagicMock(), logger=MagicMock())


def _json_out(capsys):
    return json.loads(capsys.readouterr().out)


def test_json_interface_lists_all_fields(capsys):
    cli = _make_cli()
    cli.quads.get_host.return_value = MagicMock()
    cli.quads.get_host_interface.return_value = [
        SimpleNamespace(
            name="em5",
            bios_id=None,
            mac_address="04:32:01:ab:62:f1",
            switch_ip="192.168.241.253",
            switch_port="et-0/0/12:1",
            switch_vendor=None,
            speed=25,
            vendor=None,
            pxe_boot=False,
            maintenance=False,
        ),
        SimpleNamespace(
            name="em1",
            bios_id="ABC123",
            mac_address="b4:83:51:10:77:70",
            switch_ip="192.168.241.253",
            switch_port="et-0/0/12:2",
            switch_vendor="arista",
            speed=25,
            vendor="Intel Corporation",
            pxe_boot=True,
            maintenance=False,
        ),
    ]

    assert cli.run("interface", {"host": "host1", "json_output": True}) == 0

    assert _json_out(capsys) == [
        {
            "name": "em1",
            "bios_id": "ABC123",
            "mac_address": "b4:83:51:10:77:70",
            "switch_ip": "192.168.241.253",
            "switch_port": "et-0/0/12:2",
            "switch_vendor": "arista",
            "speed": 25,
            "vendor": "Intel Corporation",
            "pxe_boot": True,
            "maintenance": False,
        },
        {
            "name": "em5",
            "bios_id": None,
            "mac_address": "04:32:01:ab:62:f1",
            "switch_ip": "192.168.241.253",
            "switch_port": "et-0/0/12:1",
            "switch_vendor": None,
            "speed": 25,
            "vendor": None,
            "pxe_boot": False,
            "maintenance": False,
        },
    ]


def test_json_host_resources(capsys):
    cli = _make_cli()
    host = SimpleNamespace(
        memory=[SimpleNamespace(handle="DIMM_A1", size_gb=32)],
        disks=[SimpleNamespace(disk_type="SSD", size_gb=480, count=2)],
        processors=[
            SimpleNamespace(
                handle="CPU0",
                vendor="Intel",
                product="Xeon",
                cores=16,
                threads=32,
                processor_type="CPU",
            ),
            SimpleNamespace(
                handle="GPU0",
                vendor="NVIDIA",
                product="A100",
                cores=108,
                threads=216,
                processor_type="GPU",
            ),
        ],
    )
    cli.quads.get_host.return_value = host

    assert cli.run("memory", {"host": "host1", "json_output": True}) == 0
    assert _json_out(capsys) == [{"handle": "DIMM_A1", "size_gb": 32}]

    assert cli.run("disks", {"host": "host1", "json_output": True}) == 0
    assert _json_out(capsys) == [{"name": "disk0", "disk_type": "SSD", "size_gb": 480, "count": 2}]

    assert cli.run("cpu", {"host": "host1", "json_output": True}) == 0
    assert _json_out(capsys) == [
        {
            "handle": "CPU0",
            "vendor": "Intel",
            "product": "Xeon",
            "cores": 16,
            "threads": 32,
            "processor_type": "CPU",
        }
    ]

    assert cli.run("gpu", {"host": "host1", "json_output": True}) == 0
    assert _json_out(capsys) == [
        {
            "handle": "GPU0",
            "vendor": "NVIDIA",
            "product": "A100",
            "cores": 108,
            "threads": 216,
            "processor_type": "GPU",
        }
    ]


@pytest.mark.parametrize("action", sorted(QuadsCli.JSON_ACTIONS))
def test_json_empty_results_emit_empty_list(action, capsys):
    cli = _make_cli()
    cli.quads.get_host.return_value = SimpleNamespace(memory=[], disks=[], processors=[])
    cli.quads.get_host_interface.return_value = []
    cli.quads.get_os_list.return_value = []
    cli.quads.get_active_assignments.return_value = []
    cli.quads.get_expiring_schedules.return_value = []
    cli.quads.get_summary.return_value.json.return_value = []

    assert cli.run(action, {"host": "host1", "json_output": True}) == 0
    assert _json_out(capsys) == []


def test_every_table_action_supports_json():
    table_actions = {
        name[len("action_") :]
        for name, method in inspect.getmembers(QuadsCli, inspect.isfunction)
        if name.startswith("action_") and "RichTable(" in inspect.getsource(method)
    }

    assert table_actions - {"show_progress"} == set(QuadsCli.JSON_ACTIONS)


def test_json_expirations_reports_one_row_per_cloud(capsys):
    cli = _make_cli()
    assignment = {
        "ticket": "1234",
        "owner": "owner",
        "description": "description",
        "qinq": 0,
        "wipe": True,
        "ostype": "RHEL 9.4",
        "boot_order": "foreman",
        "provisioned": True,
        "validated": False,
        "is_self_schedule": False,
        "cloud": {"name": "cloud02"},
    }
    schedule = Schedule().from_dict(
        {
            "start": "Tue, 24 Nov 2026 09:00:00 GMT",
            "end": "Tue, 24 Nov 2026 10:00:00 GMT",
            "assignment": assignment,
            "host": {"name": "host1"},
        }
    )
    same_cloud = Schedule().from_dict(
        {
            "start": "Tue, 24 Nov 2026 09:00:00 GMT",
            "end": "Tue, 24 Nov 2026 12:00:00 GMT",
            "assignment": assignment,
            "host": {"name": "host2"},
        }
    )
    cli.quads.get_expiring_schedules.return_value = [schedule, same_cloud]

    assert cli.run("ls_expirations", {"json_output": True}) == 0

    assert _json_out(capsys) == [
        {
            "cloud": "cloud02",
            "ticket": "1234",
            "end": "2026-11-24T10:00:00+00:00",
            "expires_in_days": time_remaining(schedule.end)[0],
            "is_self_schedule": False,
            "owner": "owner",
            "description": "description",
            "qinq": 0,
            "wipe": True,
            "ostype": "RHEL 9.4",
            "boot_order": "foreman",
            "provisioned": True,
            "validated": False,
        }
    ]


@pytest.mark.parametrize("include_all", [False, True])
@pytest.mark.parametrize("detail", [False, True])
def test_json_summary_always_full_detail(include_all, detail, capsys):
    cli = _make_cli()
    summary_rows = [
        {
            "name": "cloud01",
            "count": 0,
            "description": "Available",
            "owner": "",
            "ticket": "",
            "ccuser": [],
            "provisioned": False,
            "validated": False,
            "is_self_schedule": False,
        },
        {
            "name": "cloud02",
            "count": 4,
            "description": "test cloud",
            "owner": "owner",
            "ticket": "1234",
            "ccuser": ["user"],
            "provisioned": True,
            "validated": True,
            "is_self_schedule": False,
        },
    ]
    cli.quads.get_summary.return_value.json.return_value = summary_rows

    assert cli.run("summary", {"json_output": True, "all": include_all, "detail": detail}) == 0

    assert _json_out(capsys) == summary_rows


def test_json_notifications(capsys):
    cli = _make_cli()
    notification = SimpleNamespace(
        fail=False,
        success=True,
        initial=False,
        pre_initial=True,
        pre=False,
        one_day=True,
        three_days=False,
        five_days=True,
        seven_days=False,
    )
    assignment = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud02"),
        ticket="42",
        owner="owner",
        description="description",
        qinq=0,
        wipe=False,
        ostype="RHEL 9.4",
        boot_order="foreman",
        is_self_schedule=False,
        provisioned=True,
        validated=True,
        notification=notification,
    )
    cli.quads.get_active_assignments.return_value = [assignment]

    assert cli.run("list_notifications", {"json_output": True}) == 0

    assert _json_out(capsys) == [
        {
            "cloud": "cloud02",
            "ticket": "42",
            "owner": "owner",
            "description": "description",
            "qinq": 0,
            "wipe": False,
            "ostype": "RHEL 9.4",
            "boot_order": "foreman",
            "is_self_schedule": False,
            "provisioned": True,
            "validated": True,
            "fail": False,
            "success": True,
            "initial": False,
            "pre_initial": True,
            "pre": False,
            "one_day": True,
            "three_days": False,
            "five_days": True,
            "seven_days": False,
        }
    ]


def test_json_os_list(capsys):
    cli = _make_cli()
    os_list = [
        {"id": 1, "title": "RHEL 9.4", "release_name": "RHEL 9.4", "family": "Red Hat Enterprise Linux"},
        {"id": 2, "title": "Fedora 41", "release_name": "Fedora", "family": "Fedora"},
    ]
    cli.quads.get_os_list.return_value = os_list

    assert cli.run("os_list", {"json_output": True}) == 0

    assert _json_out(capsys) == os_list


def test_json_rejected_for_unsupported_action():
    cli = _make_cli()

    with pytest.raises(CliException, match="--json is not supported"):
        cli.run("version", {"json_output": True})


def test_json_requires_an_action():
    cli = _make_cli()

    with pytest.raises(CliException, match="--json requires one of the supported actions"):
        cli.run(None, {"json_output": True})
