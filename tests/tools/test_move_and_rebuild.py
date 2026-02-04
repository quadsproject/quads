import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from datetime import datetime

from quads.server.dao.host import HostDao
from quads.server.dao.baseDao import BaseDao
from quads.tools.move_and_rebuild import move_and_rebuild
from tests.cli.config import HOST1

# Mock the external dependencies to avoid needing real hardware
@pytest.fixture
def mock_dependencies():
    with patch("quads.tools.move_and_rebuild.badfish_factory", new_callable=AsyncMock) as mock_bf, \
         patch("quads.tools.move_and_rebuild.Foreman") as mock_foreman, \
         patch("quads.tools.move_and_rebuild.IPMI") as mock_ipmi, \
         patch("quads.tools.move_and_rebuild.is_supported", return_value=True):

        # Setup Badfish mock
        bf_instance = AsyncMock()
        mock_bf.return_value = bf_instance

        # Setup Foreman mock
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

        # Setup IPMI mock
        ipmi_instance = MagicMock()
        mock_ipmi.return_value = ipmi_instance
        ipmi_instance.configure_user = AsyncMock()
        ipmi_instance.pxe_persistent = AsyncMock()

        yield

@pytest.mark.asyncio
async def test_move_and_rebuild_success_sets_provisioned_true(test_client, auth, prefill, mock_dependencies):
    """
    Test that a successful move_and_rebuild sets host.provisioned = True
    """
    # 1. Setup: Get a host and ensure it starts as unprovisioned
    host_name = "host2.example.com"  # Using host2 as it is usually in cloud01 in standard prefill
    host = HostDao.get_host(host_name)
    host.provisioned = False
    BaseDao.safe_commit()

    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    # 2. Execute: Run the tool
    # We use rebuild=True to trigger the full logic path
    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    # 3. Assert: Tool returned True
    assert result is True

    # 4. Assert: Database flag was updated
    # We must refresh the object from the DB to see the write
    BaseDao.db.session.expire(host)
    host = HostDao.get_host(host_name)

    assert host.provisioned is True
    assert host.validated is False  # Should be False as per your code
    assert host.build is True


@pytest.mark.asyncio
async def test_move_and_rebuild_failure_sets_provisioned_false(test_client, auth, prefill, mock_dependencies):
    """
    Test that a failed move_and_rebuild (e.g. Foreman fails) sets host.provisioned = False
    """
    host_name = "host2.example.com"
    host = HostDao.get_host(host_name)
    host.provisioned = True  # Start as True to prove it gets reset
    BaseDao.safe_commit()

    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    # Force a failure in Foreman
    with patch("quads.tools.move_and_rebuild.prepare_foreman_rebuild", new_callable=AsyncMock) as mock_prep:
        mock_prep.return_value = False  # Simulate failure

        result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

        assert result is False

        # Verify DB state
        BaseDao.db.session.expire(host)
        host = HostDao.get_host(host_name)

        assert host.provisioned is False
