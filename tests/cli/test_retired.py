from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.server.dao.host import HostDao
from quads.server.models import db
from tests.cli.config import HOST1
from tests.cli.test_base import TestBase


def finalizer():
    HostDao.update_host(HOST1, retired=False)


@pytest.fixture
def unretire(request):
    request.addfinalizer(finalizer)


@pytest.fixture
def retire(request):
    request.addfinalizer(finalizer)
    HostDao.update_host(HOST1, retired=True)


class TestRetired(TestBase):
    def test_mark_retired(self, unretire):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("retire")

        assert self._caplog.messages[0] == f"Host {HOST1} is now marked as retired"

        host = HostDao.get_host(HOST1)
        db.session.refresh(host)
        assert host.retired

    def test_mark_retired_already(self, retire):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("retire")

        assert self._caplog.messages[0] == f"Host {HOST1} has already been marked as retired"

        host = HostDao.get_host(HOST1)
        assert host.retired

    def test_mark_unretired(self, retire):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("unretire")

        assert self._caplog.messages[0] == f"Host {HOST1} is now marked as unretired"

        host = HostDao.get_host(HOST1)
        assert not host.retired

    def test_mark_unretired_already(self):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("unretire")

        assert self._caplog.messages[0] == f"Host {HOST1} has already been marked unretired"

        host = HostDao.get_host(HOST1)
        assert not host.retired

    def test_ls_retired(self, retire):
        self.cli_args["host"] = HOST1

        self.quads_cli_call("ls_retired")

        assert self._caplog.messages[0] == HOST1

        host = HostDao.get_host(HOST1)
        assert host.retired

    @patch("quads.quads_api.Session.get")
    def test_ls_retired_exception(self, mock_get, retire):
        mock_get.return_value.status_code = 500
        self.cli_args["host"] = HOST1
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("ls_retired")
        assert str(ex.value) == "Check the flask server logs"
