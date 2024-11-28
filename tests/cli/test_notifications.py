import pytest

from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from tests.cli.config import (
    DEFINE_CLOUD,
    FREE_CLOUD, MOD_CLOUD,
)
from tests.cli.test_base import TestBase


def finalizer():
    cloud = CloudDao.get_cloud(DEFINE_CLOUD)
    assignment = AssignmentDao.get_active_cloud_assignment(cloud)
    if assignment:
        AssignmentDao.remove_assignment(assignment.id)
    if cloud:
        CloudDao.remove_cloud(DEFINE_CLOUD)


def finalizer_free():
    cloud_free = CloudDao.get_cloud(FREE_CLOUD)
    if cloud_free:
        CloudDao.remove_cloud(FREE_CLOUD)


@pytest.fixture(autouse=True)
def remove_cloud(request):
    finalizer()
    request.addfinalizer(finalizer)


@pytest.fixture(autouse=True)
def define_cloud(request):
    CloudDao.create_cloud(DEFINE_CLOUD)
    request.addfinalizer(finalizer)


@pytest.fixture(autouse=True)
def define_free_cloud(request):
    cloud = CloudDao.create_cloud(FREE_CLOUD)
    assignment = AssignmentDao.get_active_cloud_assignment(cloud)
    if assignment:
        AssignmentDao.update_assignment(assignment.id, **{"active": False})
    request.addfinalizer(finalizer_free)


class TestNotifications(TestBase):
    def test_ls_notifications(self):
        self.quads_cli_call("list_notifications")
        assert len(self._caplog.messages) == 1

    def test_ls_cloud_notification(self):
        self.cli_args["cloud"] = MOD_CLOUD
        self.quads_cli_call("list_notifications")
        messages = self._caplog.messages
        assert MOD_CLOUD in messages[0]

    def test_ls_non_exists_cloud_notifications(self):
        self.cli_args["cloud"] = FREE_CLOUD
        self.quads_cli_call("list_notifications")
        messages = self._caplog.messages
        assert messages[0] == f"WARNING: there are no current or future schedules for {FREE_CLOUD}"

    def test_modify_notification(self):
        self.cli_args["cloud"] = MOD_CLOUD
        self.cli_args["fail"] = 'true'
        self.quads_cli_call("modify_notification")
        messages = self._caplog.messages
        assert f"{MOD_CLOUD}, Notification updated successfully".strip() == messages[0].strip()

    def test_modify_non_exists_cloud_notification(self):
        self.cli_args["cloud"] = FREE_CLOUD
        self.cli_args["fail"] = 'true'
        self.quads_cli_call("modify_notification")
        messages = self._caplog.messages
        assert f"{FREE_CLOUD}, No active cloud assignment found".strip() == messages[0].strip()
