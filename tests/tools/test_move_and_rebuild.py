import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
import pytest

from quads.server.dao.host import HostDao
from quads.server.dao.baseDao import BaseDao
from quads.server.models import db
from quads.tools.move_and_rebuild import move_and_rebuild

prefill_settings = ["clouds, vlans, hosts, assignments, schedules"]


@pytest.fixture
def mock_dependencies():
    def side_effect_update_host(hostname, data):
        host = HostDao.get_host(hostname)
        for key, value in data.items():
            if hasattr(host, key):
                setattr(host, key, value)
        BaseDao.safe_commit()
        return MagicMock(status_code=200)

    with patch("quads.tools.move_and_rebuild.badfish_factory", new_callable=AsyncMock) as mock_bf, \
         patch("quads.tools.move_and_rebuild.Foreman") as mock_foreman, \
         patch("quads.tools.move_and_rebuild.IPMI") as mock_ipmi, \
         patch("quads.tools.move_and_rebuild.is_supported", return_value=True), \
         patch("quads.tools.move_and_rebuild.quads.update_host", side_effect=side_effect_update_host), \
         patch("quads.tools.move_and_rebuild.quads.update_schedule"):

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

        yield


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_success_sets_provisioned_true(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    host = HostDao.get_host(host_name)
    host.provisioned = False
    BaseDao.safe_commit()

    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

    assert result is True

    db.session.expire(host)
    host = HostDao.get_host(host_name)

    assert host.provisioned is True
    assert host.validated is False
    assert host.build is True


@pytest.mark.asyncio
@pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
async def test_move_and_rebuild_failure_sets_provisioned_false(test_client, auth, prefill, mock_dependencies):
    host_name = "host2.example.com"
    host = HostDao.get_host(host_name)
    host.provisioned = True
    BaseDao.safe_commit()

    target_cloud = "cloud02"
    semaphore = asyncio.Semaphore(1)

    with patch("quads.tools.move_and_rebuild.prepare_foreman_rebuild", new_callable=AsyncMock) as mock_prep:
        mock_prep.return_value = False

        result = await move_and_rebuild(host_name, target_cloud, semaphore, rebuild=True)

        assert result is False

        db.session.expire(host)
        host = HostDao.get_host(host_name)

        assert host.provisioned is False
