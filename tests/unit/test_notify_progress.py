from unittest.mock import MagicMock, patch

from quads.tools.notify import main as notify_main


class TestNotifyMain:
    @patch("quads.tools.notify.quads")
    def test_main_progress_advances_per_assignment(self, mock_quads):
        ass1 = MagicMock()
        ass1.cloud.name = "cloud01"
        ass1.notification.initial = True
        ass1.is_self_schedule = True
        mock_quads.get_clouds.return_value = []
        mock_quads.filter_assignments.return_value = [ass1]
        mock_quads.get_current_schedules.return_value = []

        with patch("quads.tools.notify.Progress") as mock_progress_cls:
            mock_progress = MagicMock()
            mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = 0

            notify_main()

        mock_progress.add_task.assert_any_call("Sending notifications", total=1)
        assert mock_progress.advance.call_count >= 1

    @patch("quads.tools.notify.quads")
    def test_main_progress_advances_per_cloud(self, mock_quads):
        cloud1 = MagicMock()
        cloud1.name = "cloud01"
        mock_quads.get_clouds.return_value = [cloud1]
        mock_quads.filter_assignments.return_value = []
        mock_quads.get_active_cloud_assignment.return_value = None

        with patch("quads.tools.notify.Progress") as mock_progress_cls:
            mock_progress = MagicMock()
            mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = 0

            notify_main()

        mock_progress.add_task.assert_any_call("Processing clouds", total=1)
        assert mock_progress.advance.call_count >= 1

    @patch("quads.tools.notify.quads")
    def test_main_empty_data_runs_without_error(self, mock_quads):
        mock_quads.get_clouds.return_value = []
        mock_quads.filter_assignments.return_value = []

        notify_main()
