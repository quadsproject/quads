#!/usr/bin/env python3
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
        p.hardware_initialized = True
        return p


def _mock_host(name="host01.example.com", bootmode=None):
    host = MagicMock()
    host.name = name
    host.rack = "rack01"
    host.uloc = "u10"
    host.blade = "blade1"
    host.bootmode = bootmode
    return host


class TestRebootForRebuildConditional:

    @pytest.mark.asyncio
    async def test_skip_boot_to_type_when_already_set_uefi(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Uefi",
                "OneTimeBootMode": "OneTimeUefiBootSeq",
                "OneTimeUefiBootSeqDev": "NIC.Integrated.1-1-1",
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.boot_to_type.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_skip_boot_to_type_when_already_set_bios(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Bios",
                "OneTimeBootMode": "OneTimeBootSeq",
                "OneTimeBootSeqDev": "NIC.Integrated.1-1-1",
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.boot_to_type.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_boot_to_type_when_mode_disabled(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Uefi",
                "OneTimeBootMode": "Disabled",
                "OneTimeUefiBootSeqDev": None,
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.boot_to_type.assert_called_once()
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_boot_to_type_when_attribute_returns_none(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.boot_to_type.assert_called_once()
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_boot_to_type_when_query_raises(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=Exception("BMC unreachable"))
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.boot_to_type.assert_called_once()
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_boot_to_type_failure_returns_false(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=False)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is False
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_reboot_server_failure_returns_false(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=False)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}

            result = await plugin.reboot_for_rebuild(_mock_host(), "/path/interfaces.yml")

        assert result is False
        plugin.hardware_dispatcher.boot_to_type.assert_called_once()
        plugin.logger.error.assert_called_once()


class TestBootmodeApplication:

    @pytest.mark.asyncio
    async def test_sets_bootmode_when_mismatched(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Bios",
                "OneTimeBootMode": "Disabled",
                "OneTimeBootSeqDev": None,
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode="Uefi"), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Uefi"})
        plugin.hardware_dispatcher.reboot_server.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_bootmode_when_matching(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Uefi",
                "OneTimeBootMode": "Disabled",
                "OneTimeUefiBootSeqDev": None,
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode="Uefi"), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_bootmode_when_unset(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode=None), "/path/interfaces.yml")

        assert result is True
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootmode_read_failure_returns_false(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode="Uefi"), "/path/interfaces.yml")

        assert result is False
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootmode_set_failure_returns_false(self, plugin):
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Bios",
                "OneTimeBootMode": "Disabled",
                "OneTimeBootSeqDev": None,
            }.get(attr)
        )
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=False)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode="Uefi"), "/path/interfaces.yml")

        assert result is False
        plugin.hardware_dispatcher.reboot_server.assert_not_called()
