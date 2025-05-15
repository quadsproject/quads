import pytest

from quads.quads_api import APIBadRequest
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.tools import logger
from quads.tools.external.switch import Switch


def test_verify_false():
    with pytest.raises(APIBadRequest):
        switch = Switch(logger)
        switch.verify("host.verify.example.com.example.com")


def test_verify_empty():
    CloudDao.create_cloud("cloudverify")
    HostDao.create_host("host.verify.example.com", "r640", "unittest", "cloudverify")
    switch = Switch(logger)
    response = switch.verify("host.verify.example.com")
    assert not response
    HostDao.remove_host("host.verify.example.com")
    CloudDao.remove_cloud("cloudverify")
