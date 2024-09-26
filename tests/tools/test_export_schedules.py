import os

from unittest.mock import patch, MagicMock
from quads.quads_api import APIServerException, APIBadRequest
from quads.tools.export_current_schedules import export_current_schedules
from tests.tools.test_base import TestBase


class TestExportSchedules(TestBase):
    output_file = os.path.join(os.path.dirname(__file__), "artifacts/output.yaml")

    @patch("quads.tools.export_current_schedules.QuadsApi")
    def test_export_current_schedules_with_valid_data(self, mock_quads_api):
        mock_quads_api.get_future_schedules.return_value = [
            MagicMock(
                assignment={
                    "cloud": {"name": "cloud1"},
                    "description": "description1",
                    "owner": "owner1",
                    "ticket": "ticket1",
                    "qinq": "qinq1",
                    "wipe": "wipe1",
                    "ccuser": ["ccuser1"],
                    "vlan": {"vlan_id": "vlan_id1"},
                },
                start="Mon, 01 Jan 2022 00:00:00 GMT",
                end="Tue, 02 Jan 2022 00:00:00 GMT",
                build_start="Mon, 01 Jan 2022 00:00:00 GMT",
                build_end="Tue, 02 Jan 2022 00:00:00 GMT",
                host={"name": "host1", "cloud": {"name": "cloud1"}, "default_cloud": {"name": "cloud1"}},
            )
        ]
        export_current_schedules(self.output_file)

    @patch("quads.tools.export_current_schedules.QuadsApi")
    def test_export_current_schedules_with_no_future_schedules(self, mock_quads_api):
        mock_quads_api.get_future_schedules.return_value = []
        export_current_schedules(self.output_file)

    @patch("quads.tools.export_current_schedules.QuadsApi.get_future_schedules")
    def test_export_current_schedules_with_api_exception(self, mock_quads_api, caplog):
        mock_quads_api.side_effect = APIServerException("API Server Exception")
        export_current_schedules(self.output_file)
        assert "Failed to get future schedules: API Server Exception" in caplog.text

    @patch("quads.tools.export_current_schedules.QuadsApi.get_future_schedules")
    def test_export_current_schedules_with_api_bad_request(self, mock_quads_api, caplog):
        mock_quads_api.side_effect = APIBadRequest("API Bad Request")
        export_current_schedules(self.output_file)
        assert "Failed to get future schedules: API Bad Request" in caplog.text
