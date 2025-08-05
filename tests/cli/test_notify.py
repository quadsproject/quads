from unittest.mock import patch

from quads.config import Config
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.cloud import CloudDao
from quads.server.models import db
from tests.cli.config import NetcatStub
from tests.cli.test_base import TestBase


class TestNotify(TestBase):
    @patch("quads.tools.external.postman.SMTP")
    def test_notify_not_validated(self, mocked_smtp):
        Config.__setattr__("foreman_unavailable", True)
        mocked_smtp()

        self.quads_cli_call("notify")

        cloud = CloudDao.get_cloud(name="cloud99")
        ass = AssignmentDao.get_active_cloud_assignment(cloud=cloud)
        db.session.refresh(ass)
        assert ass.notification.pre_initial is True
        assert self._caplog.messages == [
            "=============== Future Initial Message",
            "=============== Future Initial Message",
            "Notifications sent out.",
        ]

    @patch("quads.tools.notify.Netcat", NetcatStub)
    @patch("quads.tools.external.postman.SMTP")
    def test_notify_validated(self, mocked_smtp):
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("webhook_notify", True)
        mocked_smtp()
        cloud = CloudDao.get_cloud(name="cloud99")
        ass = AssignmentDao.get_active_cloud_assignment(cloud=cloud)
        setattr(ass, "validated", True)
        BaseDao.safe_commit()

        self.quads_cli_call("notify")
        db.session.refresh(ass)
        assert ass.notification.pre_initial is True
        assert ass.notification.initial is True
        assert self._caplog.messages[1:] == [
            "Beep boop we can't communicate with your webhook.",
            "Notifications sent out.",
        ]
