import logging

import pytest

from quads.quads_api import APIBadRequest
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.tools.external.switch import Switch

logger = logging.getLogger(__name__)
logger.propagate = True


@pytest.fixture
def cloud_name():
    return "cloudverify"


@pytest.fixture
def host_name():
    return "host.verify.example.com"


@pytest.fixture
def setup_cloud_and_host(cloud_name, host_name):
    CloudDao.create_cloud(cloud_name)
    HostDao.create_host(host_name, "r640", "unittest", cloud_name)

    yield

    HostDao.remove_host(host_name)
    CloudDao.remove_cloud(cloud_name)


@pytest.fixture
def switch():
    return Switch(logger)


def test_verify_false(switch):
    with pytest.raises(APIBadRequest):
        switch.verify("host.verify.example.com")


def test_verify_empty(setup_cloud_and_host, host_name, switch):
    response = switch.verify(host_name)
    assert not response
