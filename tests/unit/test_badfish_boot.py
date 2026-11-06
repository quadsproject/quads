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
        p.bootmode_poll_interval = 0
        p.hardware_dispatcher.get_pending_bios_attribute = AsyncMock(return_value=None)
        p.hardware_dispatcher.clear_job_queue = AsyncMock(return_value=True)
        p.hardware_dispatcher.clear_pending_bios = AsyncMock(return_value=True)
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

    @pytest.mark.asyncio
    async def test_does_not_requeue_bootmode(self, plugin):
        plugin._apply_bootmode_with_retry = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(
            side_effect=lambda attr: {
                "BootMode": "Bios",
                "OneTimeBootMode": "Disabled",
                "OneTimeBootSeqDev": None,
            }.get(attr)
        )
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.boot_to_type = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result = await plugin.reboot_for_rebuild(_mock_host(bootmode="Uefi"), "/path/interfaces.yml")

        assert result is True
        plugin._apply_bootmode_with_retry.assert_not_awaited()
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.boot_to_type.assert_called_once()


class TestPrepareHostHardwareBootmode:

    @pytest.mark.asyncio
    async def test_init_failure_returns_false_none(self, plugin):
        plugin.hardware_initialized = False
        plugin.hardware_dispatcher.init = AsyncMock(return_value=False)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor is None
        plugin.hardware_dispatcher.init.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_applies_bootmode_before_boot_order_selection(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.change_boot = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Bios"})
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)
        plugin.hardware_dispatcher.change_boot.assert_not_called()

    @pytest.mark.asyncio
    async def test_applies_bootmode_before_change_boot(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        calls = []
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(
            side_effect=lambda attributes: calls.append("set_bios") or True
        )
        plugin.hardware_dispatcher.reboot_server = AsyncMock(
            side_effect=lambda graceful=False: calls.append("reboot") or True
        )
        plugin.hardware_dispatcher.change_boot = AsyncMock(
            side_effect=lambda order, path: calls.append("change_boot") or True
        )

        with (
            patch("quads.plugins.builtin.release.standard.Config") as mock_cfg,
            patch("quads.plugins.builtin.release.standard.asyncio.sleep", new=AsyncMock()),
        ):
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "alternate", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        assert calls == ["set_bios", "reboot", "change_boot"]

    @pytest.mark.asyncio
    async def test_matching_pending_bootmode_is_reapplied(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        plugin.hardware_dispatcher.get_pending_bios_attribute = AsyncMock(return_value="Bios")
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Bios"})
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)

    @pytest.mark.asyncio
    async def test_conflicting_pending_bootmode_aborts(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value="Bios")
        plugin.hardware_dispatcher.get_pending_bios_attribute = AsyncMock(return_value="Uefi")
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        plugin.hardware_dispatcher.clear_job_queue.assert_awaited_once()
        plugin.hardware_dispatcher.clear_pending_bios.assert_awaited_once()
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_clears_conflicting_pending_bootmode_and_retries(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        plugin.hardware_dispatcher.get_pending_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.clear_job_queue.assert_awaited_once()
        plugin.hardware_dispatcher.clear_pending_bios.assert_awaited_once()
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Bios"})
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)

    @pytest.mark.asyncio
    async def test_retries_set_after_clearing_job_queue(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Bios"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(side_effect=[False, True])
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.clear_job_queue.assert_awaited_once()
        assert plugin.hardware_dispatcher.set_bios_attribute.await_count == 2
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)

    @pytest.mark.asyncio
    async def test_pending_bootmode_read_failure_aborts(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value="Uefi")
        plugin.hardware_dispatcher.get_pending_bios_attribute = AsyncMock(side_effect=RuntimeError("BMC unavailable"))
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_retries_transient_bootmode_read_failure(self, plugin):
        plugin.bootmode_poll_interval = 0
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=[None, "Uefi", "Bios"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        assert plugin.hardware_dispatcher.get_bios_attribute.await_count == 3
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Bios"})

    @pytest.mark.asyncio
    async def test_does_not_reboot_when_bootmode_matches(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value="Bios")
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_unset_bootmode_skips_apply(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock()
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode=None), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        plugin.hardware_dispatcher.get_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootmode_set_failure_aborts_without_reboot(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=False)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        plugin.hardware_dispatcher.reboot_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_bootmode_reboot_failure_aborts(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=False)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        plugin.hardware_dispatcher.set_bios_attribute.assert_awaited_once_with({"BootMode": "Bios"})
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootmode_apply_timeout_aborts(self, plugin):
        plugin.bootmode_apply_timeout = 0
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        plugin.hardware_dispatcher.reboot_server.assert_awaited_once_with(graceful=False)
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_bootmode_read_failure_aborts(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(return_value=None)
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is False
        assert vendor == "Dell"
        assert plugin.hardware_dispatcher.get_bios_attribute.await_count == 3
        plugin.hardware_dispatcher.set_bios_attribute.assert_not_called()
        plugin.hardware_dispatcher.reboot_server.assert_not_called()
        plugin.logger.error.assert_called_once()

    @pytest.mark.asyncio
    async def test_waits_across_polls_for_bootmode(self, plugin):
        plugin.hardware_dispatcher.get_vendor.return_value = "Dell"
        plugin.hardware_dispatcher.get_bios_attribute = AsyncMock(side_effect=["Uefi", "Uefi", "Bios"])
        plugin.hardware_dispatcher.set_bios_attribute = AsyncMock(return_value=True)
        plugin.hardware_dispatcher.reboot_server = AsyncMock(return_value=True)

        with patch("quads.plugins.builtin.release.standard.Config") as mock_cfg:
            mock_cfg.plugins = {"foreman": {"default_boot_order": "foreman"}}
            result, vendor = await plugin.prepare_host_hardware(
                _mock_host(bootmode="Bios"), "foreman", "/path/interfaces.yml"
            )

        assert result is True
        assert vendor == "Dell"
        assert plugin.hardware_dispatcher.get_bios_attribute.await_count == 3
