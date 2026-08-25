import asyncio
import copy
from types import SimpleNamespace

import pytest

from quads.config import Config
from quads.web.controller.CloudOperations import CloudOperations


class MockResponse:
    def __init__(self, payload):
        self.payload = payload
        self.status_code = 200

    def json(self):
        return self.payload


def make_quads_api(clouds):
    return SimpleNamespace(
        get_summary=lambda data: MockResponse(copy.deepcopy(clouds)),
        get_current_schedules=lambda data: [],
        filter_hosts=lambda data: [],
    )


def make_cloud(name, owner, ccuser, validated=True, count=5):
    return {
        "name": name,
        "count": count,
        "description": f"{name} desc",
        "owner": owner,
        "ccuser": ccuser,
        "ticket": "",
        "provisioned": True,
        "validated": validated,
        "is_self_schedule": False,
    }


def run_report(quads_api, username, roles=None):
    report = asyncio.run(CloudOperations(quads_api=quads_api).get_cloud_summary_report(username, roles))
    return report


def find_cloud(report, name):
    for bucket in ("my_assignments", "other_assignments"):
        for cloud in report.get(bucket, []):
            if cloud["name"] == name:
                return cloud
    return None


def bucket_of(report, name):
    for bucket in ("my_assignments", "other_assignments"):
        if any(cloud["name"] == name for cloud in report.get(bucket, [])):
            return bucket
    return None


@pytest.fixture(autouse=True)
def enable_management():
    Config.__setattr__("openstack_management", True)
    Config.__setattr__("openshift_management", True)
    yield


CLOUDS = [
    make_cloud("cloud02", "alice", ["bob", "carol@example.com"]),
    make_cloud("cloud03", "eve", []),
    make_cloud("cloud04", "eve", [], validated=False),
]


def test_owner_sees_links():
    report = run_report(make_quads_api(CLOUDS), "alice")
    cloud02 = find_cloud(report, "cloud02")
    assert cloud02["href_url_openstack"] == f"{Config['quads_url']}/instack/cloud02_instackenv.json"
    assert cloud02["href_url_text_openstack"] == "download"
    assert cloud02["href_color"] == "link-success"


def test_ccuser_sees_links():
    report = run_report(make_quads_api(CLOUDS), "bob")
    cloud02 = find_cloud(report, "cloud02")
    assert cloud02["href_url_openshift"] == f"{Config['quads_url']}/instack/cloud02_ocpinventory.json"
    assert cloud02["href_url_text_openshift"] == "download"


def test_non_owner_gets_no_links():
    report = run_report(make_quads_api(CLOUDS), "mallory")
    cloud02 = find_cloud(report, "cloud02")
    assert "href_url_openstack" not in cloud02
    assert "href_url_openshift" not in cloud02
    assert "href_url_text_openstack" not in cloud02
    assert "href_color" not in cloud02


def test_admin_sees_links_without_owning():
    report = run_report(make_quads_api(CLOUDS), "zed", roles=["admin"])
    cloud03 = find_cloud(report, "cloud03")
    assert "href_url_openstack" in cloud03
    assert bucket_of(report, "cloud03") == "other_assignments"


def test_anonymous_gets_no_links():
    report = run_report(make_quads_api(CLOUDS), None)
    assert "all_assignments" in report
    for cloud in report["all_assignments"]:
        assert "href_url_openstack" not in cloud
        assert "href_url_openshift" not in cloud


def test_spit_includes_ccusers():
    report = run_report(make_quads_api(CLOUDS), "bob")
    assert bucket_of(report, "cloud02") == "my_assignments"
    assert bucket_of(report, "cloud03") == "other_assignments"


def test_my_split_does_not_use_admin_bypass():
    report = run_report(make_quads_api(CLOUDS), "zed", roles=["admin"])
    assert bucket_of(report, "cloud03") == "other_assignments"


def test_validating_cloud_keeps_placeholder():
    report = run_report(make_quads_api(CLOUDS), "eve")
    cloud04 = find_cloud(report, "cloud04")
    assert cloud04["href_url_text_openstack"] == "validating..."
    assert cloud04["href_url_openstack"] == "#"
    assert cloud04["href_color"] == "link-danger"
