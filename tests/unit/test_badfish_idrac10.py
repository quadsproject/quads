#!/usr/bin/env python3
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.tools.external.badfish import Badfish, BadfishException

HOST_URI = "https://mgmt-host.example.com"
REDFISH_URI = "/redfish/v1"
SYSTEM_RESOURCE = "/redfish/v1/Systems/System.Embedded.1"
MANAGER_RESOURCE = "/redfish/v1/Managers/iDRAC.Embedded.1"
MANAGER_VM = "%s/VirtualMedia" % MANAGER_RESOURCE
SYSTEM_VM = "%s/VirtualMedia" % SYSTEM_RESOURCE
MEMBER_CD = "%s/CD" % MANAGER_VM
MEMBER_REMOVABLE = "%s/RemovableDisk" % MANAGER_VM
MEMBER_ONE = "%s/1" % SYSTEM_VM
MEMBER_TWO = "%s/2" % SYSTEM_VM
OEM_OSD = "%s/Oem/Dell/DellOSDeploymentService" % SYSTEM_RESOURCE
LEGACY_OSD = "%s/Dell/Systems/System.Embedded.1/DellOSDeploymentService" % REDFISH_URI
OPTICAL_MEDIA_TYPES = ["CD", "DVD", "USBStick"]

BOOT_SOURCES = "%s/BootSources" % SYSTEM_RESOURCE
OEM_BOOT_SOURCES = "%s/Oem/Dell/DellBootSources" % SYSTEM_RESOURCE
BOOT_SOURCES_SETTINGS = "%s/Settings" % OEM_BOOT_SOURCES
UEFI_BOOT_SEQ = [
    {"Index": 0, "Name": "NIC.PxeDevice.1-1", "Enabled": True, "Id": "id-1"},
    {"Index": 1, "Name": "RAID.SL.1-2", "Enabled": True, "Id": "id-2"},
    {"Index": 2, "Name": "NIC.PxeDevice.2-1", "Enabled": True, "Id": "id-3"},
]
BOOT_SOURCES_RESP = {"Attributes": {"UefiBootSeq": UEFI_BOOT_SEQ}}


def url(path):
    return "%s%s" % (HOST_URI, path)


def make_response(status=200, payload=None):
    response = MagicMock()
    response.status = status
    response.headers = {}
    response.text = AsyncMock(return_value=json.dumps(payload if payload is not None else {}))
    return response


def router(responses, default_status=404):
    """Return a side effect resolving request URIs against a response map."""

    def _resolve(uri, *args, **kwargs):
        if uri in responses:
            return responses[uri]
        return make_response(default_status, {"error": {"code": "Base.1.18.GeneralError"}})

    return _resolve


def media_collection(*members):
    return {"Members": [{"@odata.id": member} for member in members]}


@pytest.fixture
def badfish_instance():
    with patch("quads.tools.external.badfish.logger"):
        badfish = Badfish("mgmt-host.example.com", "r1", "u1", "b1", "user", "pass", loop=MagicMock())
    badfish.system_resource = SYSTEM_RESOURCE
    badfish.manager_resource = MANAGER_RESOURCE
    badfish.vendor = "Dell"
    return badfish


class TestIsOpticalMedia:
    def test_matches_by_id(self):
        assert Badfish.is_optical_media("CD") is True

    def test_ignores_removable_disk(self):
        assert Badfish.is_optical_media("RemovableDisk") is False

    def test_matches_by_media_types(self):
        assert Badfish.is_optical_media("1", OPTICAL_MEDIA_TYPES) is True

    def test_ignores_usb_only_media_types(self):
        assert Badfish.is_optical_media("2", ["USBStick"]) is False

    def test_ignores_numeric_id_without_media_types(self):
        assert Badfish.is_optical_media("1") is False


class TestFindVirtualMediaResource:
    @pytest.mark.asyncio
    async def test_manager_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(MANAGER_VM): make_response()}))

        assert await badfish_instance.find_virtual_media_resource() == MANAGER_VM

    @pytest.mark.asyncio
    async def test_falls_back_to_system_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(SYSTEM_VM): make_response()}))

        assert await badfish_instance.find_virtual_media_resource() == SYSTEM_VM

    @pytest.mark.asyncio
    async def test_supermicro_resource(self, badfish_instance):
        badfish_instance.vendor = "Supermicro"
        vm1 = "%s/VM1" % MANAGER_RESOURCE
        badfish_instance.get_request = AsyncMock(side_effect=router({url(vm1): make_response()}))

        assert await badfish_instance.find_virtual_media_resource() == vm1

    @pytest.mark.asyncio
    async def test_cached_resource(self, badfish_instance):
        badfish_instance.virtual_media_resource = SYSTEM_VM
        badfish_instance.get_request = AsyncMock()

        assert await badfish_instance.find_virtual_media_resource() == SYSTEM_VM
        badfish_instance.get_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_resource_found(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({}))

        with pytest.raises(BadfishException):
            await badfish_instance.find_virtual_media_resource()


class TestGetVirtualMediaDevice:
    @pytest.mark.asyncio
    async def test_device_by_name(self, badfish_instance):
        badfish_instance.get_request = AsyncMock()

        assert await badfish_instance.get_virtual_media_device([MEMBER_REMOVABLE, MEMBER_CD]) == MEMBER_CD
        badfish_instance.get_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_device_by_media_types(self, badfish_instance):
        member_data = make_response(payload={"Id": "1", "MediaTypes": OPTICAL_MEDIA_TYPES})
        badfish_instance.get_request = AsyncMock(side_effect=router({url(MEMBER_ONE): member_data}))

        assert await badfish_instance.get_virtual_media_device([MEMBER_ONE, MEMBER_TWO]) == MEMBER_ONE

    @pytest.mark.asyncio
    async def test_no_optical_device(self, badfish_instance):
        member_data = make_response(payload={"Id": "1", "MediaTypes": ["USBStick"]})
        badfish_instance.get_request = AsyncMock(side_effect=router({url(MEMBER_ONE): member_data}))

        with pytest.raises(BadfishException):
            await badfish_instance.get_virtual_media_device([MEMBER_ONE])


class TestVirtualMediaActions:
    @pytest.mark.asyncio
    async def test_check_virtual_media_numeric_ids(self, badfish_instance):
        badfish_instance.virtual_media_resource = SYSTEM_VM
        responses = {
            url(SYSTEM_VM): make_response(payload=media_collection(MEMBER_ONE, MEMBER_TWO)),
            url(MEMBER_ONE): make_response(payload={"Id": "1", "Inserted": True, "MediaTypes": OPTICAL_MEDIA_TYPES}),
            url(MEMBER_TWO): make_response(payload={"Id": "2", "Inserted": False, "MediaTypes": OPTICAL_MEDIA_TYPES}),
        }
        badfish_instance.get_request = AsyncMock(side_effect=router(responses))

        assert await badfish_instance.check_virtual_media() is True

    @pytest.mark.asyncio
    async def test_unmount_virtual_media_numeric_ids(self, badfish_instance):
        badfish_instance.virtual_media_resource = SYSTEM_VM
        responses = {
            url(SYSTEM_VM): make_response(payload=media_collection(MEMBER_ONE, MEMBER_TWO)),
            url(MEMBER_ONE): make_response(payload={"Id": "1", "MediaTypes": OPTICAL_MEDIA_TYPES}),
        }
        badfish_instance.get_request = AsyncMock(side_effect=router(responses))
        badfish_instance.post_request = AsyncMock(return_value=make_response(status=204))

        assert await badfish_instance.unmount_virtual_media() is True
        assert badfish_instance.post_request.call_args[0][0] == url("%s/Actions/VirtualMedia.EjectMedia" % MEMBER_ONE)

    @pytest.mark.asyncio
    async def test_mount_virtual_media_numeric_ids(self, badfish_instance):
        badfish_instance.virtual_media_resource = SYSTEM_VM
        responses = {
            url(SYSTEM_VM): make_response(payload=media_collection(MEMBER_ONE, MEMBER_TWO)),
            url(MEMBER_ONE): make_response(payload={"Id": "1", "MediaTypes": OPTICAL_MEDIA_TYPES}),
        }
        badfish_instance.get_request = AsyncMock(side_effect=router(responses))
        badfish_instance.post_request = AsyncMock(return_value=make_response(status=204))

        assert await badfish_instance.mount_virtual_media("http://example.com/boot.iso") is True
        assert badfish_instance.post_request.call_args[0][0] == url("%s/Actions/VirtualMedia.InsertMedia" % MEMBER_ONE)


class TestOsDeploymentResource:
    @pytest.mark.asyncio
    async def test_oem_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_OSD): make_response()}))

        assert await badfish_instance.find_os_deployment_resource() == OEM_OSD

    @pytest.mark.asyncio
    async def test_falls_back_to_legacy_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(LEGACY_OSD): make_response()}))

        assert await badfish_instance.find_os_deployment_resource() == LEGACY_OSD

    @pytest.mark.asyncio
    async def test_resources_follow_discovered_system_id(self, badfish_instance):
        badfish_instance.system_resource = "/redfish/v1/Systems/System.Embedded.2"
        legacy = "%s/Dell/Systems/System.Embedded.2/DellOSDeploymentService" % REDFISH_URI
        badfish_instance.get_request = AsyncMock(side_effect=router({url(legacy): make_response()}))

        assert await badfish_instance.find_os_deployment_resource() == legacy

    @pytest.mark.asyncio
    async def test_cached_resource(self, badfish_instance):
        badfish_instance.os_deployment_resource = OEM_OSD
        badfish_instance.get_request = AsyncMock()

        assert await badfish_instance.find_os_deployment_resource() == OEM_OSD
        badfish_instance.get_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_unsupported_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({}))

        assert await badfish_instance.find_os_deployment_resource() is None
        assert await badfish_instance.check_os_deployment_support() is False

    @pytest.mark.asyncio
    async def test_detach_remote_image_uses_resolved_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_OSD): make_response()}))
        badfish_instance.post_request = AsyncMock(return_value=make_response())

        assert await badfish_instance.detach_remote_image() is True
        expected = url("%s/Actions/DellOSDeploymentService.DetachISOImage" % OEM_OSD)
        assert badfish_instance.post_request.call_args[0][0] == expected

    @pytest.mark.asyncio
    async def test_check_remote_image_uses_resolved_resource(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_OSD): make_response()}))
        badfish_instance.post_request = AsyncMock(return_value=make_response(payload={"ISOAttachStatus": "Attached"}))

        assert await badfish_instance.check_remote_image() is True
        expected = url("%s/Actions/DellOSDeploymentService.GetAttachStatus" % OEM_OSD)
        assert badfish_instance.post_request.call_args[0][0] == expected

    @pytest.mark.asyncio
    async def test_boot_remote_image_uses_resolved_resource(self, badfish_instance):
        task = "%s/TaskService/Tasks/JID_123" % REDFISH_URI
        responses = {
            url(OEM_OSD): make_response(),
            url(task): make_response(payload={"TaskStatus": "OK"}),
        }
        badfish_instance.get_request = AsyncMock(side_effect=router(responses))
        boot_response = make_response(status=202)
        boot_response.headers = {"Location": task}
        badfish_instance.post_request = AsyncMock(return_value=boot_response)

        assert await badfish_instance.boot_remote_image("server:/path/to.iso") is True
        expected = url("%s/Actions/DellOSDeploymentService.BootToNetworkISO" % OEM_OSD)
        assert badfish_instance.post_request.call_args[0][0] == expected


class TestCreateJob:
    @pytest.mark.asyncio
    async def test_already_committed_400_is_success(self, badfish_instance):
        with patch("quads.tools.external.badfish.logger") as mock_logger:
            badfish_instance.post_request = AsyncMock(
                return_value=make_response(
                    400,
                    {
                        "error": {
                            "@Message.ExtendedInfo": [
                                {
                                    "Message": "Pending configuration values are already committed, "
                                    "unable to perform another set operation."
                                }
                            ]
                        }
                    },
                )
            )

            await badfish_instance.create_job(url("%s/Oem/Dell/Jobs" % MANAGER_RESOURCE), {}, {})

            mock_logger.info.assert_any_call("BIOS config job already scheduled by settings patch; continuing.")

    @pytest.mark.asyncio
    async def test_other_400_still_errors(self, badfish_instance):
        with (
            patch("quads.tools.external.badfish.logger") as mock_logger,
            patch.object(Badfish, "error_handler", new=AsyncMock()) as mock_handler,
        ):
            badfish_instance.post_request = AsyncMock(
                return_value=make_response(400, {"error": {"code": "Base.1.18.GeneralError"}})
            )

            await badfish_instance.create_job(url("%s/Oem/Dell/Jobs" % MANAGER_RESOURCE), {}, {})

            mock_logger.error.assert_called_once()
            mock_handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_success_status(self, badfish_instance):
        with patch("quads.tools.external.badfish.logger") as mock_logger:
            badfish_instance.post_request = AsyncMock(return_value=make_response())

            await badfish_instance.create_job(url("%s/Oem/Dell/Jobs" % MANAGER_RESOURCE), {}, {})

            mock_logger.info.assert_any_call("POST command passed to create target config job.")


class TestFindBootSourcesResource:
    @pytest.mark.asyncio
    async def test_idrac9_boot_sources(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(BOOT_SOURCES): make_response()}))

        assert await badfish_instance.find_boot_sources_resource() == BOOT_SOURCES

    @pytest.mark.asyncio
    async def test_idrac10_falls_back_to_oem(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_BOOT_SOURCES): make_response()}))

        assert await badfish_instance.find_boot_sources_resource() == OEM_BOOT_SOURCES

    @pytest.mark.asyncio
    async def test_cached_resource(self, badfish_instance):
        badfish_instance.boot_sources_resource = OEM_BOOT_SOURCES
        badfish_instance.get_request = AsyncMock()

        assert await badfish_instance.find_boot_sources_resource() == OEM_BOOT_SOURCES
        badfish_instance.get_request.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_resource_found(self, badfish_instance):
        badfish_instance.get_request = AsyncMock(side_effect=router({}))

        with pytest.raises(BadfishException):
            await badfish_instance.find_boot_sources_resource()


class TestGetBootDevicesIdrac10:
    @pytest.mark.asyncio
    async def test_reads_uefi_boot_seq_from_oem_resource(self, badfish_instance):
        badfish_instance.get_boot_seq = AsyncMock(return_value="UefiBootSeq")
        badfish_instance.get_request = AsyncMock(
            side_effect=router({url(OEM_BOOT_SOURCES): make_response(payload=BOOT_SOURCES_RESP)})
        )

        await badfish_instance.get_boot_devices()

        assert badfish_instance.boot_devices == UEFI_BOOT_SEQ
        assert badfish_instance.boot_sources_resource == OEM_BOOT_SOURCES

    @pytest.mark.asyncio
    async def test_raises_when_no_boot_sources_supported(self, badfish_instance):
        badfish_instance.get_boot_seq = AsyncMock(return_value="UefiBootSeq")
        badfish_instance.get_request = AsyncMock(side_effect=router({}))

        with pytest.raises(BadfishException):
            await badfish_instance.get_boot_devices()


class TestPatchBootSeqIdrac10:
    @pytest.mark.asyncio
    async def test_patches_oem_settings_resource(self, badfish_instance):
        badfish_instance.get_boot_seq = AsyncMock(return_value="UefiBootSeq")
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_BOOT_SOURCES): make_response()}))
        badfish_instance.boot_devices = UEFI_BOOT_SEQ
        badfish_instance.patch_request = AsyncMock(return_value=make_response(status=200))

        await badfish_instance.patch_boot_seq()

        expected = url(BOOT_SOURCES_SETTINGS)
        assert badfish_instance.patch_request.call_args[0][0] == expected
        assert badfish_instance.patch_request.call_args[0][1] == {"Attributes": {"UefiBootSeq": UEFI_BOOT_SEQ}}
        assert badfish_instance.boot_sources_resource == OEM_BOOT_SOURCES
        assert badfish_instance.patch_request.await_count == 1

    @pytest.mark.asyncio
    async def test_accepts_204_no_content_as_success(self, badfish_instance):
        badfish_instance.get_boot_seq = AsyncMock(return_value="UefiBootSeq")
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_BOOT_SOURCES): make_response()}))
        badfish_instance.boot_devices = UEFI_BOOT_SEQ
        badfish_instance.patch_request = AsyncMock(return_value=make_response(status=204))

        await badfish_instance.patch_boot_seq()

        assert badfish_instance.patch_request.await_count == 1

    @pytest.mark.asyncio
    async def test_accepts_202_accepted_as_success(self, badfish_instance):
        badfish_instance.get_boot_seq = AsyncMock(return_value="UefiBootSeq")
        badfish_instance.get_request = AsyncMock(side_effect=router({url(OEM_BOOT_SOURCES): make_response()}))
        badfish_instance.boot_devices = UEFI_BOOT_SEQ
        badfish_instance.patch_request = AsyncMock(return_value=make_response(status=202))
        badfish_instance.error_handler = AsyncMock()

        await badfish_instance.patch_boot_seq()

        assert badfish_instance.patch_request.await_count == 1
        badfish_instance.error_handler.assert_not_called()
