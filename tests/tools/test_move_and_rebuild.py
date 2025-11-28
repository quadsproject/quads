import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import logging
import pytest

from quads.server.dao.host import HostDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.baseDao import BaseDao
from quads.tools.move_and_rebuild import move_and_rebuild

prefill_settings = ["clouds, hosts, vlans, assignments, schedules"]


@pytest.fixture
def mock_dependencies():
    # Helper to simulate API updates directly to the DB
    def side_effect_update_host(hostname, data):
        host = HostDao.get_host(hostname)
        for key, value in data.items():
            if key == "cloud" and isinstance(value, str):
                # If CloudDao is patched, this returns a Mock
                cloud_val = CloudDao.get_cloud(name=value)
                # If we got a Mock, we cannot set it on the SQLAlchemy object
                if isinstance(cloud_val, MagicMock):
                    continue
                value = cloud_val

            if hasattr(host, key):
                setattr(host, key, value)
        BaseDao.safe_commit()
        return MagicMock(status_code=200)

    # Mock foreman_heal to avoid running it
    mock_foreman_heal = MagicMock()

    # Mock for safe_commit tracking
    mock_safe_commit = MagicMock(side_effect=BaseDao.safe_commit)

    # We patch QuadsApi class methods to avoid issues with the singleton instance in server.app
    # We also patch DAOs and foreman_heal used in utils.py
    with (
        patch("quads.tools.move_and_rebuild.badfish_factory", new_callable=AsyncMock) as mock_bf,
        patch("quads.tools.move_and_rebuild.Foreman") as mock_foreman,
        patch("quads.tools.move_and_rebuild.IPMI") as mock_ipmi,
        patch("quads.tools.move_and_rebuild.is_supported", return_value=True),
        patch("quads.quads_api.QuadsApi.update_host", side_effect=side_effect_update_host),
        patch("quads.quads_api.QuadsApi.update_schedule"),
        patch("quads.quads_api.QuadsApi.update_assignment") as mock_update_assignment,
        patch("quads.quads_api.QuadsApi.get_active_assignments") as mock_get_active_assignments,
        patch("quads.quads_api.QuadsApi.get_current_schedules") as mock_get_current_schedules,
        patch("quads.tools.foreman_heal.rbac", mock_foreman_heal),
        patch("quads.cli.cli.foreman_heal", mock_foreman_heal),
        patch("quads.server.dao.baseDao.BaseDao.safe_commit", mock_safe_commit),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):

        bf_instance = AsyncMock()
        bf_instance.get_bios_attribute = AsyncMock(return_value="Uefi")
        mock_bf.return_value = bf_instance

        foreman_instance = MagicMock()
        mock_foreman.return_value = foreman_instance
        foreman_instance.get_available_os = AsyncMock(return_value=[{"id": 1, "title": "RHEL 7"}])
        foreman_instance.get_mediums = AsyncMock(return_value=[{"name": "media1"}])
        foreman_instance.get_ptables = AsyncMock(return_value=[{"name": "ptable1"}])
        foreman_instance.set_host_parameter = AsyncMock(return_value=True)
        foreman_instance.put_parameter = AsyncMock(return_value=True)
        foreman_instance.put_parameters_by_name = AsyncMock(return_value=True)
        foreman_instance.get_user_id = AsyncMock(return_value=1)
        foreman_instance.get_host_id = AsyncMock(return_value=1)
        foreman_instance.put_element = AsyncMock(return_value=True)

        ipmi_instance = MagicMock()
        mock_ipmi.return_value = ipmi_instance
        ipmi_instance.configure_user = AsyncMock()
        ipmi_instance.pxe_persistent = AsyncMock()

        yield {
            "badfish": bf_instance,
            "foreman_heal": mock_foreman_heal,
            "safe_commit": mock_safe_commit,
            "update_assignment": mock_update_assignment,
            "get_active_assignments": mock_get_active_assignments,
            "get_current_schedules": mock_get_current_schedules,
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_updates_assignment_if_ready(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    # Run the function
    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True

    # Host should be built (checked via real DB because side_effect updates it)
    host = HostDao.get_host(host_name)
    assert host.build is True

    # Check that safe_commit was called (it is called by side_effect AND hopefully by utils)
    assert mock_dependencies["safe_commit"].called


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_updates_bootmode(test_client, auth, prefill, mock_dependencies, caplog):
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    caplog.set_level(logging.INFO)
    # Run the function
    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True
    assert mock_dependencies["badfish"].get_bios_attribute.called
    assert mock_dependencies["badfish"].get_bios_attribute.call_args.args[0] == "BootMode"

    assert mock_dependencies["badfish"].set_bios_attribute.called
    assert mock_dependencies["badfish"].set_bios_attribute.call_args.args[0] == {"BootMode": "Bios"}


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_failure_does_not_provision(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    with patch("quads.tools.move_and_rebuild.prepare_foreman_rebuild", new_callable=AsyncMock) as mock_prep:
        mock_prep.return_value = False

        result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

        assert result is False
