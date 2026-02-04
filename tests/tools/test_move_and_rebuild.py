import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, ANY
import pytest

from quads.server.dao.host import HostDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.baseDao import BaseDao
from quads.server.models import db
from quads.tools.move_and_rebuild import move_and_rebuild

prefill_settings = ["clouds", "vlans", "hosts", "assignments", "schedules"]


@pytest.fixture
def mock_dependencies():
    # Helper to simulate API updates directly to the DB
    def side_effect_update_host(hostname, data):
        host = HostDao.get_host(hostname)
        for key, value in data.items():
            if key == "cloud" and isinstance(value, str):
                value = CloudDao.get_cloud(name=value)

            if hasattr(host, key):
                setattr(host, key, value)
        BaseDao.safe_commit()
        return MagicMock(status_code=200)

    with patch("quads.tools.move_and_rebuild.badfish_factory", new_callable=AsyncMock) as mock_bf, \
         patch("quads.tools.move_and_rebuild.Foreman") as mock_foreman, \
         patch("quads.tools.move_and_rebuild.IPMI") as mock_ipmi, \
         patch("quads.tools.move_and_rebuild.is_supported", return_value=True), \
         patch("quads.tools.move_and_rebuild.quads.update_host", side_effect=side_effect_update_host), \
         patch("quads.tools.move_and_rebuild.quads.update_schedule"), \
         patch("quads.tools.move_and_rebuild.quads.update_assignment") as mock_update_assign, \
         patch("quads.tools.move_and_rebuild.quads.get_active_cloud_assignment") as mock_get_assign, \
         patch("quads.tools.move_and_rebuild.quads.get_current_schedules") as mock_get_schedules:

        bf_instance = AsyncMock()
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
            "update_assignment": mock_update_assign,
            "get_assignment": mock_get_assign,
            "get_schedules": mock_get_schedules
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_success_sets_assignment_provisioned_all_hosts_ready(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    # Setup assignment mock
    mock_ass = MagicMock()
    mock_ass.id = 123
    mock_dependencies["get_assignment"].return_value = mock_ass

    # Setup schedules mock - all hosts ready
    # Schedule 1: The host we are moving (will be updated to build=True by the function)
    sched1 = MagicMock()
    sched1.host.build = True
    sched1.host.validated = False

    # Schedule 2: Peer host, already ready
    sched2 = MagicMock()
    sched2.host.build = True
    sched2.host.validated = False

    mock_dependencies["get_schedules"].return_value = [sched1, sched2]

    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True

    # Check Host state
    host = HostDao.get_host(host_name)
    assert host.build is True

    # Check Assignment state updated
    mock_dependencies["update_assignment"].assert_called_with(123, {"provisioned": True})


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_success_waits_for_peers(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    mock_ass = MagicMock()
    mock_ass.id = 123
    mock_dependencies["get_assignment"].return_value = mock_ass

    # Setup schedules mock - peer NOT ready
    sched1 = MagicMock()
    sched1.host.build = True

    sched2 = MagicMock()
    sched2.host.build = False  # Peer is still building
    sched2.host.validated = False

    mock_dependencies["get_schedules"].return_value = [sched1, sched2]

    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True

    # Host updated locally
    host = HostDao.get_host(host_name)
    assert host.build is True

    # Assignment NOT updated
    mock_dependencies["update_assignment"].assert_not_called()


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

        # Assignment NOT updated
        mock_dependencies["update_assignment"].assert_not_called()
