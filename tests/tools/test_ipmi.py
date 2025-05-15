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
        mock_process.communicate.return_value = (b"IPMI output", None)
        mock_subprocess.return_value = mock_process

        arguments = ["test", "arguments"]
        await ipmi_instance.execute(arguments)

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
        mock_subprocess.assert_called_once_with(*expected_cmd, stdout=asyncio.subprocess.PIPE)
        ipmi_instance.logger.debug.assert_called()

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
    async def test_configure_user_with_ticket(self, mock_execute, ipmi_instance):
        result = await ipmi_instance.configure_user(3, "new-password", ticket="ticket123")

        assert result is True
        mock_execute.assert_any_call(["user", "set", "password", "3", "new-password"])
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
