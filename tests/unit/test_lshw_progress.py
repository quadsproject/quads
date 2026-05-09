from unittest.mock import MagicMock, patch

from quads.tools.lshw import main as lshw_main


class TestLshwMainProgress:
    @patch("quads.tools.lshw.run_lshw")
    @patch("quads.tools.lshw.quads")
    def test_main_progress_advances_per_host(self, mock_quads, mock_run_lshw):
        host1 = MagicMock()
        host1.name = "host1.example.com"
        host2 = MagicMock()
        host2.name = "host2.example.com"
        mock_quads.get_cloud.return_value = MagicMock(name="cloud01")
        mock_quads.filter_hosts.return_value = [host1, host2]

        with patch("quads.tools.lshw.Progress") as mock_progress_cls:
            mock_progress = MagicMock()
            mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = 0

            lshw_main()

        mock_progress.add_task.assert_called_once_with("Collecting lshw", total=2)
        assert mock_progress.advance.call_count == 2

    @patch("quads.tools.lshw.run_lshw")
    @patch("quads.tools.lshw.quads")
    def test_main_no_hosts_no_progress(self, mock_quads, mock_run_lshw):
        mock_quads.get_cloud.return_value = MagicMock(name="cloud01")
        mock_quads.filter_hosts.return_value = []

        with patch("quads.tools.lshw.Progress") as mock_progress_cls:
            mock_progress = MagicMock()
            mock_progress_cls.return_value.__enter__ = MagicMock(return_value=mock_progress)
            mock_progress_cls.return_value.__exit__ = MagicMock(return_value=False)
            mock_progress.add_task.return_value = 0

            lshw_main()

        mock_progress.add_task.assert_called_once_with("Collecting lshw", total=0)
        mock_progress.advance.assert_not_called()
