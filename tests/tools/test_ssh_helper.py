from unittest.mock import MagicMock, patch

import pytest
from paramiko import SSHException

from quads.tools.external.ssh_helper import SSHHelper, SSHHelperException
from tests.tools.test_base import TestBase


class TestSSHHelper(TestBase):
    @patch("quads.tools.external.ssh_helper.SSHHelper.connect")
    def test_connect_with_valid_credentials(self, mock_connect):
        mock_connect.return_value = MagicMock()
        ssh_helper = SSHHelper("valid_host", "valid_user", "valid_password")
        assert ssh_helper.ssh is not None

    @patch("quads.tools.external.ssh_helper.SSHHelper.connect")
    def test_connect_exception(self, mock_connect):
        mock_connect.side_effect = SSHException("Invalid credentials")
        with pytest.raises(SSHException) as ex:
            SSHHelper("invalid_host", "invalid_user", "invalid_password")
        assert str(ex.value) == "Invalid credentials"

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    @patch("quads.tools.external.ssh_helper.os.path.exists")
    @patch("quads.tools.external.ssh_helper.open")
    def test_connect_exception_ssh(self, mock_open, mock_os, mock_client, mock_config):
        mock_os.return_value = True
        mock_config.return_value = MagicMock()
        mock_client.return_value.connect.side_effect = SSHException("Something wong")
        with pytest.raises(SSHHelperException) as ex:
            SSHHelper("invalid_host", "invalid_user", "invalid_password")
        assert str(ex.value) == "invalid_host: Something wong"

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    def test_run_cmd_with_error(self, mock_client, mock_config):
        mock_config.return_value = MagicMock()
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = ["Error here"]
        mock_client.return_value.exec_command.return_value = (
            MagicMock(),
            MagicMock(),
            stderr_mock,
        )
        ssh_helper = SSHHelper("invalid_host", "invalid_user", "invalid_password")
        result, error = ssh_helper.run_cmd("ls")
        assert not result
        assert error == ["Error here"]

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    def test_run_cmd(self, mock_client, mock_config):
        mock_config.return_value = MagicMock()
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = []
        stdout_mock = MagicMock()
        stdout_mock.channel.recv_exit_status.return_value = 0
        mock_client.return_value.exec_command.return_value = (
            MagicMock(),
            stdout_mock,
            stderr_mock,
        )
        ssh_helper = SSHHelper("invalid_host", "invalid_user", "invalid_password")
        result, error = ssh_helper.run_cmd("ls")
        assert result

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    @patch("quads.tools.external.ssh_helper.open")
    def test_copy_ssh_key(self, mock_open, mock_client, mock_config):
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = []
        mock_config.return_value = MagicMock()
        mock_client.return_value.exec_command.return_value = (
            MagicMock(),
            MagicMock(),
            stderr_mock,
        )
        ssh_helper = SSHHelper("invalid_host", "invalid_user", "invalid_password")
        ssh_helper.copy_ssh_key("ssh_key")
        assert self._caplog.messages[0] == "Your key was copied successfully"

    @patch("quads.tools.external.ssh_helper.SSHConfig")
    @patch("quads.tools.external.ssh_helper.SSHClient")
    @patch("quads.tools.external.ssh_helper.open")
    def test_copy_ssh_key_error(self, mock_open, mock_client, mock_config):
        stderr_mock = MagicMock()
        stderr_mock.readlines.return_value = ["Error here"]
        mock_open.return_value.__enter__.return_value.readline.return_value = "ssh-rsa"
        mock_config.return_value = MagicMock()
        mock_client.return_value.exec_command.return_value = (
            MagicMock(),
            MagicMock(),
            stderr_mock,
        )
        ssh_helper = SSHHelper("invalid_host", "invalid_user", "invalid_password")
        ssh_helper.copy_ssh_key("ssh_key")
        assert self._caplog.messages[0] == "There was something wrong with your request"
        assert self._caplog.messages[1] == "Error here"
