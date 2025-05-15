import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest
from paramiko.ssh_exception import SSHException

from quads.tools.lshw import main as lshw_main
from quads.tools.lshw import run_lshw


class TestLshw(object):
    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    def test_run_lshw(self, mock_client, mock_config):
        mock_config.return_value = MagicMock()
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = ["Error here"]
        mock_client.return_value.exec_command.return_value = (
            MagicMock(),
            MagicMock(),
            stderr_mock,
        )
        temp_filename = tempfile.mktemp()

        temp_filepath = os.path.join(tempfile.gettempdir(), temp_filename)
        run_lshw("host.example.com", temp_filepath)
        assert os.path.exists(temp_filepath)

    @patch("quads.tools.external.ssh_helper.SSHHelper.connect")
    def test_run_lshw_exception(self, mock_connect):
        mock_connect.side_effect = SSHException("Invalid credentials")
        temp_filename = tempfile.mktemp()
        temp_filepath = os.path.join(tempfile.gettempdir(), temp_filename)
        response = run_lshw("host.example.com", temp_filepath)
        assert not response

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    def test_run_lshw_without_output(self, mock_client, mock_config):
        mock_config.return_value = MagicMock()
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = ""
        stdout_mock = MagicMock()
        stdout_mock.channel.recv_exit_status.return_value = 0
        stdout_mock.readlines.return_value = ""
        mock_client.return_value.exec_command.return_value = [
            MagicMock(),
            stdout_mock,
            stderr_mock,
        ]
        temp_filename = tempfile.mktemp()

        temp_filepath = os.path.join(tempfile.gettempdir(), temp_filename)
        run_lshw("host.example.com", temp_filepath)
        assert not os.path.exists(temp_filepath)

    @patch(
        "quads.tools.lshw.LSHW_OUTPUT_DIR",
        new_callable=lambda: os.path.join(os.path.dirname(__file__), "../artifacts"),
    )
    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    @pytest.mark.asyncio
    def test_main(self, mock_client, mock_config, mock_dir):
        mock_config.return_value = MagicMock()
        mock_client.return_value.exec_command.return_value = [
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]

        lshw_main()
