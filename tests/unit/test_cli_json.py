"""Tests for --json output of the table-producing CLI actions (issue #755)."""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from quads.cli import QuadsCli
from quads.exceptions import CliException


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
            speed=25,
            vendor="Intel Corporation",
            pxe_boot=True,
            maintenance=False,
        ),
    ]

    assert cli.run("interface", {"host": "host1", "json_output": True}) == 0

    out = capsys.readouterr().out
    assert "\U0001F18E" not in out
    data = json.loads(out)
    assert [row["name"] for row in data] == ["em1", "em5"]
    assert data[0]["bios_id"] == "ABC123"
    assert data[0]["pxe_boot"] is True
    assert data[1]["mac_address"] == "04:32:01:ab:62:f1"


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
    data = _json_out(capsys)
    assert len(data) == 1
    assert data[0]["handle"] == "CPU0"
    assert data[0]["processor_type"] == "CPU"

    assert cli.run("gpu", {"host": "host1", "json_output": True}) == 0
    data = _json_out(capsys)
    assert len(data) == 1
    assert data[0]["handle"] == "GPU0"
    assert data[0]["processor_type"] == "GPU"


def test_json_empty_results_emit_empty_list(capsys):
    cli = _make_cli()
    host = SimpleNamespace(memory=[], disks=[], processors=[])
    cli.quads.get_host.return_value = host
    cli.quads.get_host_interface.return_value = []
    cli.quads.get_os_list.return_value = []

    for action in ("memory", "disks", "cpu", "gpu", "interface", "os_list"):
        assert cli.run(action, {"host": "host1", "json_output": True}) == 0
        assert _json_out(capsys) == []


def test_json_expirations_dedups_per_cloud(capsys):
    cli = _make_cli()
    end = datetime.now() + timedelta(days=3)
    start = datetime.now()
    assignment = SimpleNamespace(
        cloud=SimpleNamespace(name="cloud02"),
        ticket="1234",
        is_self_schedule=False,
        owner="owner",
        description="description",
        qinq=0,
        wipe=True,
        ostype="RHEL 9.4",
        boot_order="foreman",
        provisioned=True,
        validated=False,
    )
    schedule = SimpleNamespace(assignment=assignment, end=end, start=start, host=SimpleNamespace(name="host1"))
    duplicate_cloud_schedule = SimpleNamespace(
        assignment=assignment, end=end, start=start, host=SimpleNamespace(name="host2")
    )
    cli.quads.get_expiring_schedules.return_value = [schedule, duplicate_cloud_schedule]

    assert cli.run("ls_expirations", {"json_output": True}) == 0

    data = _json_out(capsys)
    assert len(data) == 1
    assert data[0]["cloud"] == "cloud02"
    assert data[0]["ticket"] == "1234"
    assert data[0]["ssm"] is False
    assert data[0]["owner"] == "owner"
    assert data[0]["host"] == "host1"
    assert datetime.fromisoformat(data[0]["end"]) == end


def test_json_summary_always_full_detail(capsys):
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

    assert cli.run("summary", {"json_output": True, "all": False, "detail": False}) == 0

    data = _json_out(capsys)
    assert data == summary_rows


def test_json_notifications(capsys):
    cli = _make_cli()
    notification = SimpleNamespace(
        fail=False,
        success=True,
        initial=True,
        pre_initial=False,
        pre=True,
        one_day=False,
        three_days=False,
        five_days=False,
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

    data = _json_out(capsys)
    assert len(data) == 1
    assert data[0]["cloud"] == "cloud02"
    assert data[0]["ticket"] == "42"
    assert data[0]["success"] is True
    assert data[0]["seven_days"] is False


def test_json_os_list(capsys):
    cli = _make_cli()
    os_list = [{"name": "RHEL 9.4", "distro": "rhel"}, {"name": "Fedora 41", "distro": "fedora"}]
    cli.quads.get_os_list.return_value = os_list

    assert cli.run("os_list", {"json_output": True}) == 0

    assert _json_out(capsys) == os_list


def test_json_rejected_for_unsupported_action():
    cli = _make_cli()

    with pytest.raises(CliException, match="--json is not supported"):
        cli.run("version", {"json_output": True})
