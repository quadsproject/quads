import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from quads.tools.external.ipmi import IPMI
from quads.config import Config


@pytest.fixture
def ipmi_instance():
    with patch("quads.tools.external.ipmi.logger"):
        return IPMI(
            host="test-host", username="test-user", password="test-password", logger=MagicMock(spec=logging.Logger)
        )


class TestIPMI:
    @pytest.mark.asyncio
    async def test_init(self, ipmi_instance):
        assert ipmi_instance.host == "test-host"
        assert ipmi_instance.username == "test-user"
        assert ipmi_instance.password == "test-password"
        assert isinstance(ipmi_instance.semaphore, asyncio.Semaphore)
        assert ipmi_instance.semaphore._value == 20

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute(self, mock_subprocess, ipmi_instance):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"IPMI output", b"")
        mock_process.returncode = 0
        mock_subprocess.return_value = mock_process

        arguments = ["test", "arguments"]
        result = await ipmi_instance.execute(arguments)

        expected_cmd = [
            "/usr/bin/ipmitool",
            "-I",
            "lanplus",
            "-H",
            f"mgmt-{ipmi_instance.host}",
            "-U",
            ipmi_instance.username,
            "-P",
            ipmi_instance.password,
        ] + arguments
        mock_subprocess.assert_called_once_with(
            *expected_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        assert result == "IPMI output"
        ipmi_instance.logger.debug.assert_called()

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_raises_on_nonzero_exit(self, mock_subprocess, ipmi_instance):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"Unable to establish session")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError, match="IPMI command failed.*rc=1.*Unable to establish session"):
            await ipmi_instance.execute(["chassis", "power", "status"])

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_stderr_in_error(self, mock_subprocess, ipmi_instance):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"stdout info", b"stderr error detail")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError, match="stderr error detail"):
            await ipmi_instance.execute(["user", "set", "password", "4", "pass"])

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_falls_back_to_stdout_on_empty_stderr(self, mock_subprocess, ipmi_instance):
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"Error: something wrong", b"")
        mock_process.returncode = 1
        mock_subprocess.return_value = mock_process

        with pytest.raises(RuntimeError, match="Error: something wrong"):
            await ipmi_instance.execute(["chassis", "power", "on"])

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    @patch("asyncio.sleep")
    async def test_reset(self, mock_sleep, mock_execute, ipmi_instance):
        await ipmi_instance.reset()

        mock_execute.assert_any_call(["chassis", "power", "off"])
        mock_sleep.assert_called_once_with(Config["ipmi_reset_sleep"])
        mock_execute.assert_any_call(["chassis", "power", "on"])
        assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    async def test_configure_user_success(self, mock_execute, ipmi_instance):
        result = await ipmi_instance.configure_user(3, "new-password")

        assert result is True
        mock_execute.assert_any_call(["user", "priv", "3", "0x4"])
        assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    async def test_configure_user_failure(self, mock_execute, ipmi_instance):
        mock_execute.side_effect = Exception("IPMI error")

        result = await ipmi_instance.configure_user(3, "new-password")

        assert result is False
        ipmi_instance.logger.error.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(IPMI, "reset")
    @patch.object(IPMI, "execute")
    async def test_pxe_persistent_success(self, mock_execute, mock_reset, ipmi_instance):
        result = await ipmi_instance.pxe_persistent()

        assert result is True
        mock_execute.assert_called_once_with(["chassis", "bootdev", "pxe", "options=persistent"])
        mock_reset.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    async def test_pxe_persistent_failure(self, mock_execute, ipmi_instance):
        mock_execute.side_effect = Exception("IPMI error")

        result = await ipmi_instance.pxe_persistent()

        assert result is False
        ipmi_instance.logger.error.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    async def test_verify_credentials_success(self, mock_execute, ipmi_instance):
        mock_execute.return_value = "Chassis Power is on"

        result = await ipmi_instance.verify_credentials()

        assert result is True
        mock_execute.assert_called_once_with(["chassis", "power", "status"])

    @pytest.mark.asyncio
    @patch.object(IPMI, "execute")
    async def test_verify_credentials_failure(self, mock_execute, ipmi_instance):
        mock_execute.side_effect = RuntimeError("IPMI command failed (rc=1): Unable to establish session")

        result = await ipmi_instance.verify_credentials()

        assert result is False
        ipmi_instance.logger.error.assert_called_once()
