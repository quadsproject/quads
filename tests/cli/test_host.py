from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.quads_api import APIServerException
from quads.server.dao.baseDao import EntryExisting
from quads.server.dao.host import HostDao
from tests.cli.config import (
    CLOUD,
    HOST_TYPE,
    DEFINE_HOST,
    MODEL1,
    HOST1,
    IFIP1,
    HOST2,
    DEFAULT_CLOUD,
)
from tests.cli.test_base import TestBase


def finalizer():
    host = HostDao.get_host(DEFINE_HOST)
    if host:
        HostDao.remove_host(name=DEFINE_HOST)


def mark_repaired():
    host = HostDao.update_host(HOST1, broken=False)
    assert not host.broken


def mark_unretired():
    host = HostDao.update_host(HOST2, retired=False)
    assert not host.retired


@pytest.fixture
def remove_host(request):
    finalizer()
    request.addfinalizer(finalizer)


@pytest.fixture
def add_host(request):
    request.addfinalizer(finalizer)

    try:
        host = HostDao.create_host(DEFINE_HOST, MODEL1, HOST_TYPE, CLOUD)
    except EntryExisting:
        host = HostDao.get_host(DEFINE_HOST)
    assert host


@pytest.fixture
def mark_host_broken(request):
    request.addfinalizer(mark_repaired)
    host = HostDao.update_host(HOST1, broken=True)
    assert host.broken


@pytest.fixture
def mark_host_retired(request):
    request.addfinalizer(mark_unretired)
    host = HostDao.update_host(HOST2, retired=True)
    assert host.retired


class TestHost(TestBase):
    def test_define_host(self, remove_host):
        self.cli_args["host"] = DEFINE_HOST
        self.cli_args["defaultcloud"] = DEFAULT_CLOUD
        self.cli_args["hosttype"] = HOST_TYPE
        self.cli_args["model"] = MODEL1

        self.quads_cli_call("hostresource")

        host = HostDao.get_host(DEFINE_HOST)
        assert host is not None
        assert host.name == DEFINE_HOST

        assert self._caplog.messages[0] == DEFINE_HOST

    @patch("quads.quads_api.QuadsApi.create_host")
    def test_define_host_exception(self, mock_create, remove_host):
        mock_create.side_effect = APIServerException("Connection Error")
        self.cli_args["host"] = DEFINE_HOST
        self.cli_args["defaultcloud"] = DEFAULT_CLOUD
        self.cli_args["hosttype"] = HOST_TYPE
        self.cli_args["model"] = MODEL1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("hostresource")

        assert str(ex.value) == "Connection Error"

    def test_define_host_missing_model(self, remove_host):
        self.cli_args["host"] = DEFINE_HOST
        self.cli_args["defaultcloud"] = DEFAULT_CLOUD
        self.cli_args["hosttype"] = HOST_TYPE
        self.cli_args["model"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("hostresource")

        assert str(ex.value) == "Missing argument: model"

    def test_define_host_no_cloud(self, remove_host):
        self.cli_args["host"] = DEFINE_HOST
        self.cli_args["defaultcloud"] = None
        self.cli_args["hosttype"] = HOST_TYPE
        self.cli_args["model"] = MODEL1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("hostresource")

        assert str(ex.value) == "Missing parameter --default-cloud"

    def test_remove_host(self, add_host):
        self.cli_args["host"] = DEFINE_HOST

        host = HostDao.get_host(DEFINE_HOST)
        assert host is not None
        assert host.name == DEFINE_HOST

        self.quads_cli_call("rmhost")

        host = HostDao.get_host(DEFINE_HOST)
        assert not host

    def test_remove_host_no_arg(self, add_host):
        self.cli_args["host"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmhost")

        assert str(ex.value) == "Missing parameter --host"

    @patch("quads.quads_api.QuadsApi.remove_host")
    def test_remove_host_exception(self, mock_remove, add_host):
        mock_remove.side_effect = APIServerException("Connection Error")
        self.cli_args["host"] = DEFINE_HOST

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rmhost")

        assert str(ex.value) == "Connection Error"

    def test_ls_host(self):
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST1
        assert self._caplog.messages[1] == HOST2

    def test_ls_host_filter(self):
        self.cli_args["filter"] = f"model=={MODEL1}"
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST1
        assert len(self._caplog.messages) == 1

    def test_ls_host_filter_bool(self, mark_host_broken):
        self.cli_args["filter"] = "broken==true"
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST1
        assert len(self._caplog.messages) == 1

    def test_ls_host_filter_bool_false(self, mark_host_broken):
        self.cli_args["filter"] = "broken==false"
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST2
        assert len(self._caplog.messages) == 1

    def test_ls_host_filter_retired(self, mark_host_retired):
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST1
        assert len(self._caplog.messages) == 1

    def test_ls_host_filter_bad_model(self, mark_host_broken):
        self.cli_args["filter"] = "model==BADMODEL"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_hosts")
        assert str(ex.value) == "Model type not recognized."

    def test_ls_host_filter_bad_op(self):
        self.cli_args["filter"] = "model=BADMODEL"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_hosts")
        assert str(ex.value) == "A filter was defined but not parsed correctly. Check filter operator."

    def test_ls_host_filter_bad_param(self):
        self.cli_args["filter"] = "badparam==badvalue"

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_hosts")
        assert str(ex.value) == "badparam is not a valid field."

    def test_ls_host_filter_interface(self):
        self.cli_args["filter"] = f"interfaces.switch_ip=={IFIP1}"
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == HOST1
        assert len(self._caplog.messages) == 1

    def test_ls_host_filter_bad_interface(self):
        self.cli_args["filter"] = "interfaces.switch_ip==10.99.99.5"
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == "No hosts found."

    def test_ls_no_host(self):
        self.quads_cli_call("ls_hosts")

        assert self._caplog.messages[0] == "No hosts found."

    def test_ls_processors(self):
        self.cli_args["host"] = HOST1
        self.quads_cli_call("processors")

        assert self._caplog.messages[0] == "processor: P1"
        assert self._caplog.messages[1] == "  vendor: Intel"
        assert self._caplog.messages[2] == "  product: i7"
        assert self._caplog.messages[3] == "  cores: 2"
        assert self._caplog.messages[4] == "  threads: 4"

    @patch("quads.quads_api.requests.Session.get")
    def test_ls_processors_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        self.cli_args["host"] = HOST1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("processors")
        assert str(ex.value) == "Check the flask server logs"

    def test_ls_processors_no_host(self):
        if self.cli_args.get("host"):
            self.cli_args.pop("host")
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("processors")

        assert str(ex.value) == "Missing option. --host option is required for --ls-processors."

    def test_ls_processors_no_processor(self):
        self.cli_args["host"] = HOST2
        self.quads_cli_call("processors")

        assert self._caplog.messages[0] == f"No processors defined for {HOST2}"

    def test_ls_memory(self):
        self.cli_args["host"] = HOST1
        self.quads_cli_call("memory")

        assert self._caplog.messages[0] == "memory: DIMM1"
        assert self._caplog.messages[1] == "  size: 2048"
        assert self._caplog.messages[2] == "memory: DIMM2"
        assert self._caplog.messages[3] == "  size: 2048"
