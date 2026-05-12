import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from quads.config import Config
from quads.exceptions import CliException
from quads.quads_api import APIServerException
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from quads.server.models import db
from tests.cli.config import CLOUD, DEFAULT_CLOUD, HOST1, HOST2, MOD_CLOUD, MODEL2
from tests.cli.test_base import TestBase


def finalizer():
    cloud = CloudDao.get_cloud(CLOUD)
    host = HostDao.get_host(HOST2)
    schedules = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

    if schedules:
        ScheduleDao.remove_schedule(schedules[0].id)
        AssignmentDao.remove_assignment(schedules[0].assignment_id)


@pytest.fixture
def define_fixture(request):
    request.addfinalizer(finalizer)

    cloud = CloudDao.get_cloud(CLOUD)
    vlan = VlanDao.create_vlan("192.168.1.1", 122, "192.168.1.1/22", "255.255.255.255", 1)
    AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], cloud.name, vlan.vlan_id)


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


class TestSchedule(TestBase):
    def test_add_schedule(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.cli_args["schedstart"] = today.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedend"] = tomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedcloud"] = CLOUD
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["omitcloud"] = None

        self.quads_cli_call("add_schedule")
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)
        assert schedule

    def test_add_schedule_host_list_not_avail(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.cli_args["schedstart"] = today.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedend"] = tomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedcloud"] = CLOUD
        self.cli_args["host"] = None
        self.cli_args["host_list"] = os.path.join(os.path.dirname(__file__), "fixtures/hostlist")
        self.cli_args["omitcloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("add_schedule")
        assert str(ex.value) == "Remove these from your host list and try again."
        assert self._caplog.messages[0] == "The following hosts are either broken or unavailable:"
        assert self._caplog.messages[1] == f"{HOST1}"
        assert self._caplog.messages[2] == f"{HOST2}"

    def test_add_schedule_host_list_file_not_found(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.cli_args["schedstart"] = today.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedend"] = tomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedcloud"] = CLOUD
        self.cli_args["host"] = None
        self.cli_args["host_list"] = os.path.join(os.path.dirname(__file__), "nonexistent.file")
        self.cli_args["omitcloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("add_schedule")
        assert str(ex.value).startswith("Could not read file: ")

    def test_add_schedule_omit(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.cli_args["schedstart"] = today.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedend"] = tomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedcloud"] = CLOUD
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["omitcloud"] = DEFAULT_CLOUD

        self.quads_cli_call("add_schedule")
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)
        assert schedule

    def test_add_missing_args(self):
        self.cli_args["schedstart"] = None
        self.cli_args["schedend"] = None
        self.cli_args["schedcloud"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["omitcloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("add_schedule")
        assert str(ex.value) == (
            "Missing option. All of these options are required for --add-schedule:\n"
            "\t--schedule-start\n"
            "\t--schedule-end\n"
            "\t--schedule-cloud"
        )

    def test_add_missing_target(self):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        self.cli_args["schedstart"] = today.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedend"] = tomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["schedcloud"] = CLOUD
        self.cli_args["host"] = None
        self.cli_args["host_list"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("add_schedule")
        assert str(ex.value) == "Missing option. --host or --host-list required."

    def test_remove_schedule(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        self.cli_args["schedid"] = schedule[0].id
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None

        self.quads_cli_call("rmschedule")
        schedule = ScheduleDao.get_schedule(int(self.cli_args["schedid"]))
        assert not schedule

    def test_remove_schedule_no_id(self, remove_fixture):
        self.cli_args["schedid"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmschedule")
        assert str(ex.value) == "Missing option --schedule-id."

    @patch("quads.quads_api.QuadsApi.remove_schedule")
    def test_remove_exception(self, mock_remove, remove_fixture):
        mock_remove.side_effect = APIServerException("Connection Error")
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        self.cli_args["schedid"] = schedule[0].id
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmschedule")
        assert str(ex.value) == "Connection Error"

    def test_mod_schedule(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(days=2)

        self.cli_args["schedid"] = _schedule[0].id
        self.cli_args["schedend"] = atomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["host_list"] = None

        self.quads_cli_call("modschedule")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%dT%H:%M") == atomorrow.strftime("%Y-%m-%dT%H:%M")

    def test_mod_schedule_no_args(self, remove_fixture):
        self.cli_args["schedstart"] = None
        self.cli_args["schedend"] = None
        self.cli_args["host_list"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modschedule")

        assert str(ex.value) == (
            "Missing option. At least one these options are required for --mod-schedule:\n"
            "\t--schedule-start\n"
            "\t--schedule-end"
        )

    def test_ls_schedule(self, remove_fixture):
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.quads_cli_call("schedule")
        assert self._caplog.messages[0] == f"Default cloud: {CLOUD}"
        assert self._caplog.messages[1] == f"Current cloud: {CLOUD}"
        assert self._caplog.messages[2].split("|")[1].startswith(" start=")

    def test_ls_schedule_date(self, remove_fixture):
        # TODO: verify this one
        date = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["datearg"] = f"{date} 22:00"
        self.quads_cli_call("schedule")
        assert self._caplog.messages[0] == f"Default cloud: {CLOUD}"
        assert self._caplog.messages[1] == f"Current cloud: {CLOUD}"
        assert self._caplog.messages[2].split("|")[1].startswith(" start=")

    @patch("quads.quads_api.QuadsApi.get_current_schedules")
    def test_ls_schedule_exception(self, mock_get, remove_fixture):
        mock_get.side_effect = APIServerException("Connection Error")
        # TODO: verify this one
        date = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["datearg"] = f"{date} 22:00"
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("schedule")
        assert str(ex.value) == "Connection Error"

    def test_host(self, remove_fixture):
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["datearg"] = None
        self.quads_cli_call("host")
        assert self._caplog.messages[0] == f"{CLOUD}"

    def test_host_date(self, remove_fixture):
        date = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["host"] = HOST2
        self.cli_args["host_list"] = None
        self.cli_args["datearg"] = f"{date} 22:00"
        self.quads_cli_call("host")
        assert self._caplog.messages[0] == f"{CLOUD}"

    def test_ls_schedule_bad_host(self, remove_fixture):
        self.cli_args["host"] = "BADHOST"
        self.cli_args["host_list"] = None
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("schedule")

        assert str(ex.value) == "Host not found: BADHOST"

    def test_ls_schedule_no_host(self, remove_fixture):
        self.cli_args["host_list"] = None
        if self.cli_args.get("host"):
            self.cli_args.pop("host")
        self.quads_cli_call("schedule")
        assert f"{DEFAULT_CLOUD}:" in self._caplog.messages


class TestLsExpirations(TestBase):
    def test_ls_expirations(self, remove_fixture):
        self.quads_cli_call("ls_expirations")
        assert any("cloud" in msg and "ticket" in msg and "days_remaining" in msg for msg in self._caplog.messages)

    def test_ls_expirations_no_schedules(self):
        self.quads_cli_call("ls_expirations")
        assert "No active schedules found." in self._caplog.messages

    @patch("quads.quads_api.QuadsApi.get_expiring_schedules")
    def test_ls_expirations_exception(self, mock_get):
        mock_get.side_effect = APIServerException("Connection Error")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_expirations")
        assert str(ex.value) == "Connection Error"


class TestExtend(TestBase):
    def test_extend_schedule(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=4)

        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["cloud"] = None

        self.quads_cli_call("extend")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d %H:%M") == atomorrow.strftime("%Y-%m-%d %H:%M")

    def test_extend_schedule_no_schedule(self, define_fixture):
        self.cli_args["weeks"] = 2
        self.cli_args["host"] = None
        self.cli_args["cloud"] = MOD_CLOUD

        self.quads_cli_call("extend")

        assert self._caplog.messages[0] == "The selected cloud does not have any active schedules"

    def test_extend_no_dates(self):
        self.cli_args["weeks"] = None
        self.cli_args["datearg"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["cloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("extend")
        assert str(ex.value) == "Missing option. Need --weeks or --date when using --extend"

    def test_extend_no_target(self):
        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["cloud"] = None
        self.cli_args["host"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("extend")
        assert str(ex.value) == "Missing option. At least one of either --host or --cloud is required."

    def test_extend_bad_weeks(self):
        self.cli_args["weeks"] = "BADWEEKS"
        self.cli_args["datearg"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["cloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("extend")
        assert str(ex.value) == "The value of --weeks must be an integer"

    def test_extend_bad_host(self):
        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["cloud"] = None
        self.cli_args["host"] = "BADHOST"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("extend")
        assert str(ex.value) == "Host not found: BADHOST"


class TestShrink(TestBase):
    @patch("quads.cli.cli.input")
    def test_shrink_schedule(self, mock_input, remove_fixture):
        mock_input.return_value = "y"
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=1)

        self.cli_args["weeks"] = 1
        self.cli_args["host"] = HOST2

        self.quads_cli_call("shrink")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d %H:%M") == atomorrow.strftime("%Y-%m-%d %H:%M")

    @patch("quads.cli.cli.input")
    def test_shrink_schedule_check(self, mock_input, remove_fixture):
        mock_input.return_value = "y"
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=1)

        self.cli_args["weeks"] = 1
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = True

        self.quads_cli_call("shrink")
        assert self._caplog.messages[0].startswith(f"Host {HOST2} can be shrunk for 1 week[s] to")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d %H:%M") != atomorrow.strftime("%Y-%m-%d %H:%M")

    @patch("quads.cli.cli.input")
    def test_shrink_date(self, mock_input, remove_fixture):
        mock_input.return_value = "y"
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=1)

        self.cli_args["datearg"] = atomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["weeks"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = False

        self.quads_cli_call("shrink")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d %H:%M") == atomorrow.strftime("%Y-%m-%d %H:%M")

    def test_shrink_date_check(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=1)

        self.cli_args["datearg"] = atomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["weeks"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = True

        self.quads_cli_call("shrink")
        assert self._caplog.messages[0].startswith(f"Host {HOST2} can be shrunk to")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d %H:%M") != atomorrow.strftime("%Y-%m-%d %H:%M")

    @patch("quads.cli.cli.input")
    def test_shrink_now(self, mock_input, remove_fixture):
        mock_input.return_value = "y"
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()

        self.cli_args["datearg"] = None
        self.cli_args["weeks"] = None
        self.cli_args["now"] = True
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = False

        self.quads_cli_call("shrink")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d") == today.strftime("%Y-%m-%d")

    def test_shrink_now_check(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        self.cli_args["datearg"] = None
        self.cli_args["weeks"] = None
        self.cli_args["now"] = True
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = True

        self.quads_cli_call("shrink")
        assert self._caplog.messages[0] == f"Host {HOST2} can be terminated now"

    @patch("quads.cli.cli.input")
    def test_shrink_now_no(self, mock_input, remove_fixture):
        mock_input.return_value = "n"
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        _schedule = ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()

        self.cli_args["datearg"] = None
        self.cli_args["weeks"] = None
        self.cli_args["now"] = True
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = False

        self.quads_cli_call("shrink")
        schedule_obj = ScheduleDao.get_schedule(_schedule[0].id)
        db.session.refresh(schedule_obj)

        assert schedule_obj.end.strftime("%Y-%m-%d") != today.strftime("%Y-%m-%d")

    def test_shrink_past_end(self, remove_fixture):
        host = HostDao.get_host(HOST2)
        cloud = CloudDao.get_cloud(CLOUD)
        ScheduleDao.get_current_schedule(host=host, cloud=cloud)

        today = datetime.now()
        atomorrow = today + timedelta(weeks=3)

        self.cli_args["datearg"] = atomorrow.strftime("%Y-%m-%d %H:%M")
        self.cli_args["weeks"] = None
        self.cli_args["now"] = True
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = False

        self.quads_cli_call("shrink")
        assert (
            self._caplog.messages[0]
            == "The following hosts cannot be shrunk past it's start date, target date means an extension or target date is earlier than 1 hour from now:"
        )
        assert self._caplog.messages[1] == HOST2
        assert len(self._caplog.messages) == 2

    def test_shrink_no_dates(self):
        self.cli_args["weeks"] = None
        self.cli_args["datearg"] = None
        self.cli_args["now"] = False
        self.cli_args["host"] = HOST2
        self.cli_args["cloud"] = None
        self.cli_args["check"] = False

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("shrink")
        assert str(ex.value) == "Missing option. Need --weeks, --date or --now when using --shrink"

    def test_shrink_no_target(self):
        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["cloud"] = None
        self.cli_args["host"] = None
        self.cli_args["check"] = False

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("shrink")
        assert str(ex.value) == "Missing option. At least one of either --host or --cloud is required"

    def test_shrink_bad_weeks(self):
        self.cli_args["weeks"] = "BADWEEKS"
        self.cli_args["datearg"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["cloud"] = None
        self.cli_args["check"] = False

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("shrink")
        assert str(ex.value) == "The value of --weeks must be an integer"

    def test_shrink_bad_host(self):
        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["cloud"] = None
        self.cli_args["host"] = "BADHOST"
        self.cli_args["check"] = False

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("shrink")
        assert str(ex.value) == "Host not found: BADHOST"

    def test_shrink_no_schedules(self):
        self.cli_args["weeks"] = 2
        self.cli_args["datearg"] = None
        self.cli_args["cloud"] = None
        self.cli_args["host"] = HOST2
        self.cli_args["check"] = False

        self.quads_cli_call("shrink")
        assert self._caplog.messages[0] == "The selected host does not have any active schedules"
        assert len(self._caplog.messages) == 1


class TestAvailable(TestBase):
    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    def test_available(self, define_fixture):
        self.cli_args["schedstart"] = None
        self.cli_args["schedend"] = None
        self.cli_args["schedcloud"] = None
        self.cli_args["omitcloud"] = None
        self.cli_args["filter"] = None

        self.quads_cli_call("available")
        assert self._caplog.messages[0] == f"{HOST2}"

    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    def test_available_filter(self, define_fixture):
        self.cli_args["schedstart"] = None
        self.cli_args["schedend"] = None
        self.cli_args["schedcloud"] = None
        self.cli_args["omitcloud"] = None
        self.cli_args["filter"] = f"model=={MODEL2}"

        self.quads_cli_call("available")
        assert self._caplog.messages[0] == f"{HOST2}"
        assert len(self._caplog.messages) == 1

    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    def test_available_dates(self, define_fixture):
        today = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["schedstart"] = f"{today} 22:00"
        self.cli_args["schedend"] = f"{today} 22:00"
        self.cli_args["omitcloud"] = None
        self.cli_args["filter"] = None

        self.quads_cli_call("available")
        assert self._caplog.messages[0] == f"{HOST2}"
        assert len(self._caplog.messages) > 0

    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    @patch("quads.quads_api.QuadsApi.filter_hosts")
    def test_available_exception(self, mock_filter, define_fixture):
        mock_filter.side_effect = APIServerException("Connection Error")
        today = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["schedstart"] = f"{today} 22:00"
        self.cli_args["schedend"] = f"{today} 22:00"
        self.cli_args["omitcloud"] = None
        self.cli_args["filter"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("available")

        assert str(ex.value) == "Connection Error"

    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    @patch("quads.quads_api.QuadsApi.filter_hosts")
    def test_available_omit(self, mock_filter, define_fixture):
        # TODO: expand this
        today = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["schedstart"] = f"{today} 22:00"
        self.cli_args["schedend"] = f"{today} 22:00"
        self.cli_args["omitcloud"] = MOD_CLOUD
        self.cli_args["filter"] = None

        self.quads_cli_call("available")
        assert len(self._caplog.messages) == 0

    @patch.object(
        Config,
        "spare_pool_name",
        CLOUD,
    )
    @patch("quads.quads_api.QuadsApi.filter_hosts")
    def test_available_omit_bad_cloud(self, mock_filter, define_fixture):
        today = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["schedstart"] = f"{today} 22:00"
        self.cli_args["schedend"] = f"{today} 22:00"
        self.cli_args["omitcloud"] = "BADCLOUD"
        self.cli_args["filter"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("available")

        assert str(ex.value) == "No clouds found with the given filters"
