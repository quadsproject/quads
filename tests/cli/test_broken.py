from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.quads_api import APIServerException
from quads.server.dao.host import HostDao
from tests.cli.config import HOST1
from tests.cli.test_base import TestBase


def finalizer():
    host = HostDao.get_host(HOST1)
    if host:
        HostDao.update_host(name=HOST1, broken=False)


@pytest.fixture
def mr_fixture(request):
    request.addfinalizer(finalizer)
    assert HostDao.update_host(name=HOST1, broken=True)


class TestBroken(TestBase):
    def test_mark_broken(self):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("mark_broken")

        assert self._caplog.messages[0] == f"Host {HOST1} is now marked as broken"

        host = HostDao.get_host(HOST1)
        assert host.broken

    def test_mark_broken_no_arg(self):
        self.cli_args["host"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("mark_broken")

        assert str(ex.value) == "Missing option. Need --host when using --mark-broken"

    def test_mark_broken_already(self, mr_fixture):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("mark_broken")

        assert self._caplog.messages[0] == f"Host {HOST1} has already been marked broken"

        host = HostDao.get_host(HOST1)
        assert host.broken

    @patch("quads.quads_api.QuadsApi.update_host")
    def test_mark_broken_exception(self, mock_update):
        mock_update.side_effect = APIServerException("Connection Error")
        self.cli_args["host"] = HOST1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("mark_broken")

        assert str(ex.value) == "Connection Error"

    def test_ls_broken(self, mr_fixture):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("ls_broken")

        assert self._caplog.messages[0] == HOST1

        host = HostDao.get_host(HOST1)
        assert host.broken

    @patch("quads.quads_api.Session.get")
    def test_ls_broken_exception(self, mock_get, mr_fixture):
        mock_get.return_value.status_code = 500
        self.cli_args["host"] = HOST1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_broken")
        assert str(ex.value) == "Check the flask server logs"


class TestRepaired(TestBase):
    def test_mark_repaired(self, mr_fixture):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("mark_repaired")

        assert self._caplog.messages[0] == f"Host {HOST1} is now marked as repaired"

        host = HostDao.get_host(HOST1)
        assert not host.broken

    def test_mark_repaired_no_arg(self):
        self.cli_args["host"] = None

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("mark_repaired")

        assert str(ex.value) == "Missing option. Need --host when using --mark-repaired"

    @patch("quads.quads_api.QuadsApi.update_host")
    def test_mark_repaired_exception(self, mock_update, mr_fixture):
        mock_update.side_effect = APIServerException("Connection Error")
        self.cli_args["host"] = HOST1

        with pytest.raises(CliException) as ex:
            self.quads_cli_call("mark_repaired")

        assert str(ex.value) == "Connection Error"

    def test_mark_repaired_not_broken(self):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("mark_repaired")

        assert self._caplog.messages[0] == f"Host {HOST1} has already been marked repaired"

        host = HostDao.get_host(HOST1)
        assert not host.broken
