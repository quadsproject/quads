import os
import tempfile
from datetime import datetime
from unittest.mock import MagicMock, patch

from rich.table import Table

import yaml

from quads.quads_api import APIBadRequest
from quads.tools.import_current_schedules import import_current_schedules


class TestImportSchedulesProgress:
    """Unit tests that mock the module-level quads instance to verify progress bar behavior."""

    def _make_yaml(self, tmpdir, clouds=None, schedules=None):
        clouds = clouds or {"cloud01": {"description": "test", "owner": "user", "ccuser": [], "qinq": 0, "ticket": "123", "wipe": False}}
        schedules = schedules or []
        data = {"clouds": clouds, "current_schedules": schedules}
        path = os.path.join(tmpdir, "input.yaml")
        with open(path, "w") as f:
            yaml.dump(data, f)
        return path

    @patch("quads.tools.import_current_schedules.quads")
    def test_progress_cloud_bar_advances(self, mock_quads):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, clouds={"cloud01": {"description": "a", "owner": "o", "ccuser": [], "qinq": 0, "ticket": "1", "wipe": False}, "cloud02": {"description": "b", "owner": "o", "ccuser": [], "qinq": 0, "ticket": "2", "wipe": False}})
            with patch("quads.tools.import_current_schedules.Progress") as mock_progress_cls:
                mock_progress = MagicMock()
                mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                mock_progress.add_task.return_value = 0

                import_current_schedules(filepath)

        mock_progress.add_task.assert_any_call("Importing clouds", total=2)
        assert mock_progress.advance.call_count == 2

    @patch("quads.tools.import_current_schedules.quads")
    def test_progress_schedule_bar_advances(self, mock_quads):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.return_value = MagicMock()

        now = datetime(2024, 8, 6, 19, 0)
        end = datetime(2024, 8, 20, 19, 0)
        schedules = [
            {"cloud": "cloud01", "host": "host1.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False},
            {"cloud": "cloud01", "host": "host2.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, schedules=schedules)
            with patch("quads.tools.import_current_schedules.Progress") as mock_progress_cls:
                mock_progress = MagicMock()
                mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
                mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
                mock_progress.add_task.return_value = 0

                import_current_schedules(filepath)

        mock_progress.add_task.assert_any_call("Importing schedules", total=2)
        assert mock_progress.advance.call_count >= 2

    @patch("quads.tools.import_current_schedules.quads")
    def test_progress_skips_undefined_host(self, mock_quads):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.side_effect = APIBadRequest("host not found")

        now = datetime(2024, 8, 6, 19, 0)
        end = datetime(2024, 8, 20, 19, 0)
        schedules = [{"cloud": "cloud01", "host": "missing.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False}]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, schedules=schedules)
            import_current_schedules(filepath)

        mock_quads.insert_schedule.assert_not_called()

    @patch("quads.tools.import_current_schedules.Console")
    @patch("quads.tools.import_current_schedules.quads")
    def test_summary_table_printed_after_import(self, mock_quads, mock_console_cls):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.return_value = MagicMock()

        mock_console = MagicMock()
        mock_console.is_terminal = True
        mock_console_cls.return_value = mock_console

        now = datetime(2024, 8, 6, 19, 0)
        end = datetime(2024, 8, 20, 19, 0)
        schedules = [
            {"cloud": "cloud01", "host": "host1.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False},
            {"cloud": "cloud01", "host": "host2.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, schedules=schedules)
            import_current_schedules(filepath)

        mock_console.print.assert_called_once()
        printed_arg = mock_console.print.call_args[0][0]
        assert isinstance(printed_arg, Table)
        assert printed_arg.row_count == 2
        assert [c.header for c in printed_arg.columns] == ["Cloud", "Host", "Start", "End"]

    @patch("quads.tools.import_current_schedules.Console")
    @patch("quads.tools.import_current_schedules.quads")
    def test_no_table_when_no_schedules(self, mock_quads, mock_console_cls):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None

        mock_console = MagicMock()
        mock_console_cls.return_value = mock_console

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, schedules=[])
            import_current_schedules(filepath)

        mock_console.print.assert_not_called()

    @patch("quads.tools.import_current_schedules.Console")
    @patch("quads.tools.import_current_schedules.quads")
    def test_plain_output_when_piped(self, mock_quads, mock_console_cls, capsys):
        mock_quads.get_cloud.return_value = None
        mock_quads.get_active_cloud_assignment.return_value = None
        mock_quads.get_host.return_value = MagicMock()

        mock_console = MagicMock()
        mock_console.is_terminal = False
        mock_console_cls.return_value = mock_console

        now = datetime(2024, 8, 6, 19, 0)
        end = datetime(2024, 8, 20, 19, 0)
        schedules = [
            {"cloud": "cloud01", "host": "host1.example.com", "start": now, "end": end, "build_start": None, "build_end": None, "moved": False},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = self._make_yaml(tmpdir, schedules=schedules)
            import_current_schedules(filepath)

        # Console.print never called for the summary table
        mock_console.print.assert_not_called()

        captured = capsys.readouterr()
        assert "cloud01\thost1.example.com" in captured.out
        assert "│" not in captured.out
