"""Tests for StandardReleasePlugin IPMI credential verification"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from quads.plugins.builtin.release.standard import StandardReleasePlugin


@pytest.fixture
def plugin():
    config = {"enabled": True}
    with (
        patch("quads.plugins.builtin.release.standard.QuadsApi"),
        patch("quads.plugins.builtin.release.standard.get_hardware_dispatcher"),
        patch("quads.plugins.builtin.release.standard.get_provisioner_dispatcher"),
    ):
        p = StandardReleasePlugin(config)
        p.initialize()
        p.logger = MagicMock(spec=logging.Logger)
        return p


class TestConfigureAndVerifyIpmi:
    """Tests for _configure_and_verify_ipmi()"""

    @pytest.mark.asyncio
    async def test_success_first_attempt(self, plugin):
        """Configure and verify succeed on first attempt"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
        ):
            mock_cfg.plugins = {"standard": {"ipmi_credential_retries": 3, "ipmi_credential_retry_delay": 1}}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            admin_ipmi = AsyncMock()
            admin_ipmi.configure_user = AsyncMock(return_value=True)
            verify_ipmi = AsyncMock()
            verify_ipmi.verify_credentials = AsyncMock(return_value=True)
            mock_ipmi_class.side_effect = [admin_ipmi, verify_ipmi]

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is admin_ipmi
            admin_ipmi.configure_user.assert_called_once_with(4, "newpass")
            verify_ipmi.verify_credentials.assert_called_once()

    @pytest.mark.asyncio
    async def test_configure_fails_then_succeeds(self, plugin):
        """configure_user fails first attempt, succeeds on retry"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_cfg.plugins = {"standard": {"ipmi_credential_retries": 3, "ipmi_credential_retry_delay": 5}}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            fail_ipmi = AsyncMock()
            fail_ipmi.configure_user = AsyncMock(return_value=False)
            ok_ipmi = AsyncMock()
            ok_ipmi.configure_user = AsyncMock(return_value=True)
            verify_ipmi = AsyncMock()
            verify_ipmi.verify_credentials = AsyncMock(return_value=True)
            mock_ipmi_class.side_effect = [fail_ipmi, ok_ipmi, verify_ipmi]

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is ok_ipmi
            mock_sleep.assert_called_once_with(5)

    @pytest.mark.asyncio
    async def test_verify_fails_then_succeeds(self, plugin):
        """configure_user succeeds but verify fails, then both succeed on retry"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_cfg.plugins = {"standard": {"ipmi_credential_retries": 3, "ipmi_credential_retry_delay": 10}}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            ipmi1 = AsyncMock()
            ipmi1.configure_user = AsyncMock(return_value=True)
            verify1 = AsyncMock()
            verify1.verify_credentials = AsyncMock(return_value=False)
            ipmi2 = AsyncMock()
            ipmi2.configure_user = AsyncMock(return_value=True)
            verify2 = AsyncMock()
            verify2.verify_credentials = AsyncMock(return_value=True)
            mock_ipmi_class.side_effect = [ipmi1, verify1, ipmi2, verify2]

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is ipmi2
            mock_sleep.assert_called_once_with(10)

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self, plugin):
        """All retries fail, returns None"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_cfg.plugins = {"standard": {"ipmi_credential_retries": 2, "ipmi_credential_retry_delay": 1}}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            fail_ipmi = AsyncMock()
            fail_ipmi.configure_user = AsyncMock(return_value=False)
            mock_ipmi_class.return_value = fail_ipmi

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is None
            assert fail_ipmi.configure_user.call_count == 2
            mock_sleep.assert_called_once_with(1)
            plugin.logger.error.assert_called_once()
            assert "after 2 attempts" in plugin.logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_sleep_after_last_attempt(self, plugin):
        """No sleep after the final failed attempt"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_cfg.plugins = {"standard": {"ipmi_credential_retries": 1, "ipmi_credential_retry_delay": 10}}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            fail_ipmi = AsyncMock()
            fail_ipmi.configure_user = AsyncMock(return_value=False)
            mock_ipmi_class.return_value = fail_ipmi

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is None
            mock_sleep.assert_not_called()

    @pytest.mark.asyncio
    async def test_config_defaults_when_standard_absent(self, plugin):
        """Falls back to defaults when standard plugin config is missing"""
        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.IPMI") as mock_ipmi_class,
        ):
            mock_cfg.plugins = {}
            mock_cfg.__getitem__ = lambda self, key: {"ipmi_cloud_username_id": 4, "ipmi_cloud_username": "quads"}[key]

            admin_ipmi = AsyncMock()
            admin_ipmi.configure_user = AsyncMock(return_value=True)
            verify_ipmi = AsyncMock()
            verify_ipmi.verify_credentials = AsyncMock(return_value=True)
            mock_ipmi_class.side_effect = [admin_ipmi, verify_ipmi]

            result = await plugin._configure_and_verify_ipmi("host1", "root", "adminpass", "newpass")

            assert result is admin_ipmi
