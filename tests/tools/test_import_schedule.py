import os
from unittest.mock import MagicMock, patch

from quads.quads_api import APIBadRequest
from quads.tools.import_current_schedules import import_current_schedules
from tests.tools.test_base import TestBase


class TestImportSchedules(TestBase):
    input_file = os.path.join(os.path.dirname(__file__), "fixtures/valid_input.yaml")

    @patch("quads.tools.import_current_schedules.quads")
    def test_import_current_schedules_with_valid_data(self, mock_quads):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.return_value = MagicMock()
        mock_quads.insert_schedule.return_value = MagicMock()
        import_current_schedules(self.input_file)

    @patch("quads.tools.import_current_schedules.quads")
    def test_import_current_schedules_with_existing_cloud_and_assignment(self, mock_quads, caplog):
        mock_quads.get_cloud.return_value = MagicMock()
        mock_quads.get_active_cloud_assignment.return_value = MagicMock()
        mock_quads.get_host.return_value = MagicMock()
        mock_quads.insert_schedule.side_effect = APIBadRequest("Host is not available for the specified date range")

        import_current_schedules(self.input_file)

        assert any("Failed to import schedule" in r.message for r in caplog.records)

    @patch("quads.tools.import_current_schedules.quads")
    def test_import_current_schedules_with_moved_schedule(self, mock_quads, caplog):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.return_value = MagicMock()
        mock_quads.insert_schedule.side_effect = APIBadRequest("Host is not available for the specified date range")

        import_current_schedules(self.input_file)

        assert any("Failed to import schedule" in r.message for r in caplog.records)
