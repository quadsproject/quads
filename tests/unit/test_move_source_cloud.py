from datetime import datetime
from unittest.mock import MagicMock, patch

from quads.server.blueprints.moves import _progress_to_dict


class TestProgressToDict:
    def _make_schedule(self, move_source_cloud=None, host_cloud="cloud01", target_cloud="cloud02"):
        schedule = MagicMock()
        schedule.id = 1
        schedule.host.name = "host1.example.com"
        schedule.host_id = 1
        schedule.host.cloud.name = host_cloud
        schedule.move_source_cloud = move_source_cloud
        schedule.assignment.cloud.name = target_cloud
        schedule.move_status = "pending"
        schedule.move_message = None
        schedule.move_error = None
        schedule.build_start = datetime(2026, 6, 10, 8, 0)
        schedule.build_end = None
        schedule.move_stage_timestamps = None
        return schedule

    def test_source_cloud_from_persisted_value(self):
        schedule = self._make_schedule(move_source_cloud="cloud01", host_cloud="cloud02")
        result = _progress_to_dict(schedule)
        assert result["source_cloud"] == "cloud01"
        assert result["target_cloud"] == "cloud02"

    def test_source_cloud_fallback_when_not_persisted(self):
        schedule = self._make_schedule(move_source_cloud=None, host_cloud="cloud01")
        result = _progress_to_dict(schedule)
        assert result["source_cloud"] == "cloud01"

    def test_persisted_source_survives_host_cloud_change(self):
        """Simulates the release plugin updating host.cloud mid-move"""
        schedule = self._make_schedule(move_source_cloud="cloud03", host_cloud="cloud04")
        result = _progress_to_dict(schedule)
        assert result["source_cloud"] == "cloud03"
        assert result["target_cloud"] == "cloud02"

    def test_all_fields_present(self):
        schedule = self._make_schedule(move_source_cloud="cloud01")
        result = _progress_to_dict(schedule)
        expected_keys = {
            "id",
            "host",
            "host_id",
            "source_cloud",
            "target_cloud",
            "status",
            "message",
            "error_message",
            "started_at",
            "completed_at",
            "stage_timestamps",
        }
        assert set(result.keys()) == expected_keys


class TestStartMoveBatchSetsSourceCloud:
    @patch("quads.server.dao.schedule.ScheduleDao.safe_commit")
    @patch("quads.server.dao.schedule.ScheduleDao.get_current_schedule")
    @patch("quads.server.dao.schedule.HostDao.get_host")
    def test_source_cloud_captured_from_host(self, mock_get_host, mock_get_sched, mock_commit):
        from quads.server.dao.schedule import ScheduleDao

        host = MagicMock()
        host.cloud.name = "cloud03"
        mock_get_host.return_value = host

        schedule = MagicMock()
        schedule.id = 42
        mock_get_sched.return_value = [schedule]

        result = ScheduleDao.start_move_batch(["host1.example.com"])

        assert schedule.move_source_cloud == "cloud03"
        assert schedule.move_status == "pending"
        assert result["host1.example.com"] == 42
