from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, PropertyMock

from quads.server.dao.schedule import ScheduleDao


class TestGetCurrentScheduleByAssignmentId:
    """Unit tests for ScheduleDao.get_current_schedule with assignment_id param."""

    @patch("quads.server.dao.schedule.db")
    def test_filters_by_assignment_id(self, mock_db):
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []

        ScheduleDao.get_current_schedule(assignment_id=42)

        mock_query.join.assert_called()
        join_args = [call.args for call in mock_query.join.call_args_list]
        assert any(arg and arg[0] is not None for arg in join_args), "Expected join on Assignment"

    @patch("quads.server.dao.schedule.db")
    def test_does_not_filter_by_cloud_when_assignment_id_given(self, mock_db):
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []

        ScheduleDao.get_current_schedule(assignment_id=42)

        filter_calls = mock_query.filter.call_args_list
        for call in filter_calls:
            for arg in call.args:
                assert "cloud" not in str(arg).lower() or "assignment" in str(arg).lower()

    @patch("quads.server.dao.schedule.db")
    def test_cloud_param_still_works(self, mock_db):
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []

        mock_cloud = MagicMock()
        ScheduleDao.get_current_schedule(cloud=mock_cloud)

        mock_query.join.assert_called()

    @patch("quads.server.dao.schedule.db")
    def test_host_param_still_works(self, mock_db):
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = []

        mock_host = MagicMock()
        ScheduleDao.get_current_schedule(host=mock_host)

        mock_query.filter.assert_called()

    @patch("quads.server.dao.schedule.db")
    def test_returns_query_results(self, mock_db):
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query

        sched1 = MagicMock()
        sched2 = MagicMock()
        mock_query.all.return_value = [sched1, sched2]

        result = ScheduleDao.get_current_schedule(assignment_id=1)

        assert result == [sched1, sched2]


class TestTerminateScheduleIsolation:
    """Regression: terminating an assignment must query schedules by
    assignment_id, not by cloud. This prevents accidentally ending
    schedules that belong to a different assignment on the same cloud."""

    @patch("quads.server.dao.schedule.db")
    def test_assignment_id_and_cloud_return_different_results(self, mock_db):
        """Simulates the bug scenario: cloud-based lookup would return
        schedules from multiple assignments, assignment_id would not."""
        sched_old = MagicMock(name="sched_old_assignment")
        sched_new = MagicMock(name="sched_new_assignment")

        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.all.return_value = [sched_old]

        result = ScheduleDao.get_current_schedule(assignment_id=1)
        assert sched_new not in result
