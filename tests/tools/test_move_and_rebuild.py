import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from quads.server.dao.host import HostDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.baseDao import BaseDao
from quads.tools.move_and_rebuild import move_and_rebuild
from quads.helpers.utils import check_assignment_provisioning_status

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

    # Mock Data Access Objects used in utils.py
    shared_get_active_assign = MagicMock()
    shared_get_cloud = MagicMock()
    shared_get_schedules = MagicMock()

    # Mock BaseDao.safe_commit to verify commits in utils.py
    mock_safe_commit = MagicMock()

    with patch("quads.tools.move_and_rebuild.badfish_factory", new_callable=AsyncMock) as mock_bf, \
         patch("quads.tools.move_and_rebuild.Foreman") as mock_foreman, \
         patch("quads.tools.move_and_rebuild.IPMI") as mock_ipmi, \
         patch("quads.tools.move_and_rebuild.is_supported", return_value=True), \
         patch("quads.tools.move_and_rebuild.quads.update_host", side_effect=side_effect_update_host), \
         patch("quads.tools.move_and_rebuild.quads.update_schedule"), \
         patch("quads.helpers.utils.BaseDao.safe_commit", mock_safe_commit), \
         patch("quads.helpers.utils.CloudDao.get_cloud", shared_get_cloud), \
         patch("quads.helpers.utils.AssignmentDao.get_active_cloud_assignment", shared_get_active_assign), \
         patch("quads.helpers.utils.ScheduleDao.get_current_schedule", shared_get_schedules), \
         patch("asyncio.sleep", new_callable=AsyncMock):

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
            "get_cloud": shared_get_cloud,
            "get_assignment": shared_get_active_assign,
            "get_schedules": shared_get_schedules,
            "safe_commit": mock_safe_commit
        }


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_updates_assignment_if_ready(test_client, auth, prefill, mock_dependencies):
    # This test verifies that if the move completes and the host is ready, the assignment IS updated.
    host_name = "host2.example.com"
    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    mock_cloud = MagicMock()
    mock_cloud.name = target_cloud
    mock_dependencies["get_cloud"].return_value = mock_cloud

    mock_ass = MagicMock()
    mock_ass.id = 123
    mock_ass.ostype = "RHEL 7"
    mock_ass.boot_order = "foreman"
    mock_ass.provisioned = False
    mock_ass.cloud.name = target_cloud
    mock_dependencies["get_assignment"].return_value = mock_ass

    # Mock schedules so that check_assignment_provisioning_status sees "built" hosts
    mock_sched = MagicMock()
    mock_sched.host.build = True
    mock_dependencies["get_schedules"].return_value = [mock_sched]

    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True

    # Host should be built
    host = HostDao.get_host(host_name)
    assert host.build is True

    # The helper logic SHOULD check and if conditions are met (mocked above), commit.
    mock_dependencies["safe_commit"].assert_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_check_assignment_provisioning_status_success(test_client, auth, prefill, mock_dependencies):
    target_cloud = "cloud02"

    mock_cloud = MagicMock()
    mock_cloud.name = target_cloud
    mock_dependencies["get_cloud"].return_value = mock_cloud

    mock_ass = MagicMock()
    mock_ass.id = 123
    mock_ass.provisioned = False
    mock_ass.cloud.name = target_cloud
    mock_dependencies["get_assignment"].return_value = mock_ass

    # All hosts ready
    sched1 = MagicMock()
    sched1.host.build = True
    sched1.host.validated = False

    sched2 = MagicMock()
    sched2.host.build = True
    sched2.host.validated = False

    mock_dependencies["get_schedules"].return_value = [sched1, sched2]

    check_assignment_provisioning_status(target_cloud)

    # Verify we set the provisioned flag
    assert mock_ass.provisioned is True
    # Verify we committed the change
    mock_dependencies["safe_commit"].assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_check_assignment_provisioning_status_waits_for_peers(test_client, auth, prefill, mock_dependencies):
    target_cloud = "cloud02"

    mock_cloud = MagicMock()
    mock_cloud.name = target_cloud
    mock_dependencies["get_cloud"].return_value = mock_cloud

    mock_ass = MagicMock()
    mock_ass.id = 123
    mock_ass.provisioned = False
    mock_dependencies["get_assignment"].return_value = mock_ass

    # Peer not ready
    sched1 = MagicMock()
    sched1.host.build = True

    sched2 = MagicMock()
    sched2.host.build = False
    sched2.host.validated = False

    mock_dependencies["get_schedules"].return_value = [sched1, sched2]

    check_assignment_provisioning_status(target_cloud)

    # Verify no change and no commit
    assert mock_ass.provisioned is False
    mock_dependencies["safe_commit"].assert_not_called()


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

        mock_dependencies["safe_commit"].assert_not_called()
