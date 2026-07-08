from datetime import datetime, timedelta

import pytest

from quads.exceptions import CliException
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from tests.cli.config import CLOUD, HOST2
from tests.cli.test_base import TestBase


def finalizer():
    cloud = CloudDao.get_cloud(CLOUD)
    host = HostDao.get_host(HOST2)
    schedules = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

    if schedules:
        ScheduleDao.remove_schedule(schedules[0].id)
        AssignmentDao.remove_assignment(schedules[0].assignment_id)


@pytest.fixture
def remove_fixture(request):
    request.addfinalizer(finalizer)

    today = datetime.now()
    tomorrow = today + timedelta(weeks=2)

    cloud = CloudDao.get_cloud(CLOUD)
    host = HostDao.get_host(HOST2)
    vlan = VlanDao.create_vlan("192.168.1.1", 122, "192.168.1.1/22", "255.255.255.255", 1)
    assignment = AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], cloud.name, vlan.vlan_id)
    schedule = ScheduleDao.create_schedule(
        today.strftime("%Y-%m-%d %H:%M"),
        tomorrow.strftime("%Y-%m-%d %H:%M"),
        assignment,
        host,
    )
    assert schedule


class TestReport(TestBase):
    def test_report_available(self, remove_fixture, capsys):
        self.quads_cli_call("report_available")
        output = capsys.readouterr().out
        assert "QUADS report for" in output
        assert "Percentage Utilized:" in output
        assert "Availability Summary" in output
        assert "Server Type" in output
        assert "R640" in output
        assert "R930" in output

    def test_report_scheduled(self, remove_fixture, capsys):
        today = datetime.now()
        self.cli_args["months"] = 12
        self.cli_args["year"] = None
        self.quads_cli_call("report_scheduled")
        output = capsys.readouterr().out
        if today.month == 1:
            past_date = f"{today.year - 1}-12"
        else:
            past_date = f"{today.year}-{today.month - 1:02d}"
        assert "Scheduled Report" in output
        assert f"{today.year}-{today.month:02d}" in output
        assert past_date in output

    def test_report_scheduled_no_args(self, remove_fixture):
        self.cli_args["months"] = None
        self.cli_args["year"] = None
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("report_scheduled")

        assert str(ex.value) == "Missing argument. --months or --year must be provided."

    def test_report_scheduled_year(self, remove_fixture, capsys):
        today = datetime.now()
        self.cli_args["months"] = None
        self.cli_args["year"] = today.year
        self.quads_cli_call("report_scheduled")
        output = capsys.readouterr().out
        if today.month == 1:
            past_date = f"{today.year - 1}-12"
        else:
            past_date = f"{today.year}-{today.month - 1:02d}"
        assert "Scheduled Report" in output
        assert f"{today.year}-{today.month:02d}" in output
        assert past_date in output

    def test_report_detailed(self, remove_fixture, capsys):
        today = datetime.now()

        self.cli_args["months"] = None
        self.cli_args["year"] = today.year
        self.quads_cli_call("report_detailed")
        output = capsys.readouterr().out
        assert "Detailed Report" in output
        assert "Owner" in output
        assert "Ticket" in output
        assert "Duration" in output
