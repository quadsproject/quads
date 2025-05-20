from datetime import datetime
from unittest.mock import patch

import pytest

from quads.exceptions import CliException
from quads.quads_api import APIServerException
from tests.cli.config import DEFAULT_CLOUD, HOST2
from tests.cli.test_base import TestBase


class TestQuads(TestBase):
    def test_default_action(self):
        self.cli_args = {}
        self.quads_cli_call(None)
        assert self._caplog.messages[0] == f"{DEFAULT_CLOUD}:"
        assert self._caplog.messages[1] == f"  - {HOST2}"

    @patch("quads.quads_api.QuadsApi.is_available")
    def test_default_action_available_exception(self, mock_is_available):
        mock_is_available.side_effect = APIServerException("Connection Error")
        self.cli_args = {}
        with pytest.raises(CliException) as ex:
            self.quads_cli_call(None)
        assert str(ex.value) == "Connection Error"

    @patch("quads.quads_api.QuadsApi.get_current_schedules")
    def test_default_action_schedules_exception(self, mock_current_schedules):
        mock_current_schedules.side_effect = APIServerException("Connection Error")
        self.cli_args = {}
        with pytest.raises(CliException) as ex:
            self.quads_cli_call(None)
        assert str(ex.value) == "Connection Error"

    @patch("quads.quads_api.Session.get")
    def test_default_action_500_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call(None)
        assert str(ex.value) == "Check the flask server logs"

    @patch("quads.quads_api.Session.get")
    def test_default_action_400_exception(self, mock_get):
        mock_get.return_value.status_code = 400
        with pytest.raises(CliException):
            self.quads_cli_call(None)

    def test_default_action_date(self):
        date = datetime.now().strftime("%Y-%m-%d")
        self.cli_args["datearg"] = f"{date} 22:00"
        self.quads_cli_call(None)

    def test_version(self):
        self.quads_cli_call("version")
        assert self._caplog.messages[0].startswith('"QUADS version')

    @patch("quads.quads_api.Session.get")
    def test_version_exception(self, mock_get):
        mock_get.return_value.status_code = 500
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("version")
        assert str(ex.value) == "Check the flask server logs"
