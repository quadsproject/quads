from datetime import datetime
from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.quads_api import APIServerException
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from tests.cli.config import (
    CLOUD,
    DEFAULT_CLOUD,
    DEFINE_CLOUD,
    FREE_CLOUD,
    HOST1,
    MOD_CLOUD,
    REMOVE_CLOUD,
)
from tests.cli.test_base import TestBase


def finalizer():
    cloud = CloudDao.get_cloud(DEFINE_CLOUD)
    assignment = AssignmentDao.get_active_cloud_assignment(cloud)
    if assignment:
        AssignmentDao.remove_assignment(assignment.id)
    if cloud:
        CloudDao.remove_cloud(DEFINE_CLOUD)


def finalizer_free():
    cloud_free = CloudDao.get_cloud(FREE_CLOUD)
    if cloud_free:
        CloudDao.remove_cloud(FREE_CLOUD)


@pytest.fixture(autouse=True)
def remove_cloud(request):
    finalizer()
    request.addfinalizer(finalizer)


@pytest.fixture(autouse=True)
def define_cloud(request):
    CloudDao.create_cloud(DEFINE_CLOUD)
    request.addfinalizer(finalizer)


@pytest.fixture(autouse=True)
def define_free_cloud(request):
    cloud = CloudDao.create_cloud(FREE_CLOUD)
    assignment = AssignmentDao.get_active_cloud_assignment(cloud)
    if assignment:
        AssignmentDao.update_assignment(assignment.id, **{"active": False})
    request.addfinalizer(finalizer_free)


class TestCloud(TestBase):
    def test_define_cloud(self, remove_cloud):
        self.cli_args["cloud"] = DEFINE_CLOUD
        self.cli_args["description"] = "Test cloud"
        self.cli_args["cloudowner"] = "scalelab"
        self.cli_args["ccusers"] = None
        self.cli_args["qinq"] = None
        self.cli_args["cloudticket"] = "1225"
        self.cli_args["force"] = True
        self.cli_args["wipe"] = True

        self.quads_cli_call("cloudresource")

        assert self._caplog.messages[0] == f"Cloud {DEFINE_CLOUD} created."

        cloud = CloudDao.get_cloud(CLOUD)
        assert cloud is not None
        assert cloud.name == CLOUD

    def test_define_cloud_invalid_vlan(self, remove_cloud):
        self.cli_args["cloud"] = DEFINE_CLOUD
        self.cli_args["description"] = "Test cloud"
        self.cli_args["cloudowner"] = "scalelab"
        self.cli_args["ccusers"] = None
        self.cli_args["qinq"] = None
        self.cli_args["cloudticket"] = "1225"
        self.cli_args["force"] = True
        self.cli_args["wipe"] = True
        self.cli_args["vlan"] = "BADVLAN"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("cloudresource")

        assert str(ex.value) == "Could not parse vlan id. Only integers accepted."

    def test_define_cloud_locked(self):
        self.cli_args["cloud"] = CLOUD
        self.cli_args["description"] = "Test cloud"
        self.cli_args["cloudowner"] = "scalelab"
        self.cli_args["ccusers"] = None
        self.cli_args["qinq"] = None
        self.cli_args["cloudticket"] = "1225"
        self.cli_args["force"] = True
        self.cli_args["wipe"] = True
        self.cli_args["vlan"] = None

        self.quads_cli_call("cloudresource")

        assert self._caplog.messages[0] == "Can't redefine cloud:"
        assert self._caplog.messages[1].startswith(f"{CLOUD} (reserved: ")

    def test_remove_cloud(self, define_cloud):
        self.cli_args["cloud"] = REMOVE_CLOUD

        self.quads_cli_call("rmcloud")

        rm_cloud = CloudDao.get_cloud(REMOVE_CLOUD)

        assert not rm_cloud

    def test_remove_cloud_no_arg(self, define_cloud):
        self.cli_args["cloud"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmcloud")

        assert str(ex.value) == "Missing parameter --cloud"

    def test_remove_cloud_active_assignment(self, define_cloud):
        self.cli_args["cloud"] = CLOUD

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmcloud")

        assert str(ex.value) == f"There is an active cloud assignment for {CLOUD}"

    @patch("quads.quads_api.QuadsApi.remove_cloud")
    def test_remove_cloud_exception(self, mock_remove, define_cloud):
        mock_remove.side_effect = APIServerException("Connection Error")
        self.cli_args["cloud"] = DEFAULT_CLOUD

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmcloud")

        assert str(ex.value) == "Connection Error"

    @patch("quads.quads_api.QuadsApi.get_active_cloud_assignment")
    def test_remove_assignment_exception(self, mock_ass, define_cloud):
        mock_ass.side_effect = APIServerException("Connection Error")
        self.cli_args["cloud"] = DEFAULT_CLOUD

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmcloud")

        assert str(ex.value) == "Connection Error"

    def test_mod_cloud(self):
        new_description = "Modified description"
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = 4321

        self.quads_cli_call("modcloud")

        assert self._caplog.messages[0] == "Cloud modified successfully"

        cloud = CloudDao.get_cloud(MOD_CLOUD)
        assert cloud

        assignment = AssignmentDao.get_active_cloud_assignment(cloud)
        assert assignment
        assert assignment.description == new_description
        assert assignment.ticket == "4321"

    def test_mod_bad_cloud(self):
        new_description = "Modified description"
        self.cli_args["cloud"] = "BADCLOUD"
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = 4321

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modcloud")

        assert str(ex.value) == "Cloud not found: BADCLOUD"

    def test_mod_cloud_no_assignment(self):
        new_description = "Modified description"
        self.cli_args["cloud"] = DEFAULT_CLOUD
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modcloud")

        assert str(ex.value) == f"No active cloud assignment for {DEFAULT_CLOUD}"

    @patch("quads.quads_api.QuadsApi.update_assignment")
    def test_mod_cloud_exception(self, mock_update):
        mock_update.side_effect = APIServerException("Connection Error")
        new_description = "Modified description"
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modcloud")

        assert str(ex.value) == "Connection Error"

    @patch("quads.quads_api.QuadsApi.update_assignment")
    def test_mod_cloud_exception_ticket(self, mock_update):
        mock_update.side_effect = APIServerException("Connection Error")
        new_description = "Modified description"
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = 4321

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("modcloud")

        assert str(ex.value) == "Connection Error"

    def test_mod_cloud_bad_vlan(self):
        new_description = "Modified description"
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["description"] = new_description
        self.cli_args["cloudowner"] = None
        self.cli_args["ccusers"] = None
        self.cli_args["cloudticket"] = None
        self.cli_args["vlan"] = "BADVLAN"

        self.quads_cli_call("modcloud")

        assert self._caplog.messages[0] == "Cloud modified successfully"
        cloud = CloudDao.get_cloud(MOD_CLOUD)
        assignment = AssignmentDao.get_active_cloud_assignment(cloud)
        assert assignment
        assert assignment.vlan is None

    @patch("quads.quads_api.Session.get")
    def test_ls_no_clouds(self, mock_get):
        mock_get.return_value.json.return_value = []
        self.quads_cli_call("ls_clouds")

        assert self._caplog.messages[0] == "No clouds found."

    def test_ls_clouds(self):
        self.quads_cli_call("ls_clouds")

        assert self._caplog.messages[0] == DEFAULT_CLOUD
        assert self._caplog.messages[1] == MOD_CLOUD
        assert self._caplog.messages[2] == FREE_CLOUD
        assert self._caplog.messages[3] == CLOUD

    @patch("quads.quads_api.Session.get")
    def test_ls_clouds_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_clouds")
        assert str(ex.value) == "Check the flask server logs"

    def test_ls_wipe(self):
        self.quads_cli_call("wipe")

        assert self._caplog.messages[0] == f"{CLOUD}: False"

    def test_ls_ticket(self):
        self.quads_cli_call("ticket")

        assert self._caplog.messages[0] == f"{CLOUD}: 1234"

    def test_ls_owner(self):
        self.quads_cli_call("owner")

        assert self._caplog.messages[0] == f"{CLOUD}: test"

    @patch("quads.quads_api.Session.get")
    def test_ls_owner_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("owner")
        assert str(ex.value) == "Check the flask server logs"

    def test_ls_qinq(self):
        self.quads_cli_call("qinq")

        assert self._caplog.messages[0] == f"{CLOUD}: 0"

    def test_ls_cc_users(self):
        self.quads_cli_call("ccuser")

        assert self._caplog.messages[0] == f"{CLOUD}: ['']"

    def test_ls_vlan(self):
        self.quads_cli_call("ls_vlan")

        assert self._caplog.messages[0] == f"1: {CLOUD}"

    @patch("quads.quads_api.Session.get")
    def test_ls_vlan_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_vlan")
        assert str(ex.value) == "Check the flask server logs"

    @patch("quads.quads_api.QuadsApi.filter_assignments")
    def test_ls_vlan_filter_exception(self, mock_filter):
        mock_filter.side_effect = APIServerException("Connection Error")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_vlan")
        assert str(ex.value) == "Connection Error"

    @patch("quads.quads_api.Session.get")
    def test_ls_vlan_no_vlans(self, mock_get):
        self.quads_cli_call("ls_vlan")

        assert self._caplog.messages[0] == "No VLANs found."

    def test_free_cloud(self, define_free_cloud):
        self.quads_cli_call("free_cloud")

        assert self._caplog.messages[1].startswith(f"{FREE_CLOUD} (reserved: ")
        assert self._caplog.messages[1].endswith("min remaining)")

    @patch("quads.quads_api.Session.get")
    def test_free_cloud_exception(self, mock_get, define_free_cloud):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("free_cloud")
        assert str(ex.value) == "Check the flask server logs"


class TestCloudOnly(TestBase):
    def test_cloud_only(self):
        self.cli_args["cloud"] = CLOUD
        self.cli_args["datearg"] = None
        self.cli_args["filter"] = None
        self.quads_cli_call("cloudonly")
        assert self._caplog.messages[0] == f"{HOST1}"

    def test_cloud_only_filter_some(self):
        self.cli_args["cloud"] = CLOUD
        self.cli_args["datearg"] = None
        self.cli_args["filter"] = "model==R640"
        self.quads_cli_call("cloudonly")
        assert self._caplog.messages[0] == f"{HOST1}"

    def test_cloud_only_filter_none(self):
        self.cli_args["cloud"] = CLOUD
        self.cli_args["datearg"] = None
        self.cli_args["filter"] = "model==R930"
        self.quads_cli_call("cloudonly")
        assert len(self._caplog.messages) == 0

    def test_cloud_not_found(self):
        self.cli_args["cloud"] = "BADCLOUD"
        self.cli_args["datearg"] = None
        self.cli_args["filter"] = None
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("cloudonly")
            assert str(ex) == "Cloud not found: BADCLOUD"

    def test_cloud_date(self):
        date = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["cloud"] = CLOUD
        self.cli_args["datearg"] = f"{date} 22:00"
        self.cli_args["filter"] = None
        self.quads_cli_call("cloudonly")
        assert self._caplog.messages[0] == f"{HOST1}"

    def test_cloud_no_schedule(self):
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["datearg"] = None
        self.cli_args["filter"] = None
        self.quads_cli_call("cloudonly")
        assert len(self._caplog.messages) == 0
