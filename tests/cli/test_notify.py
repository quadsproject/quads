from unittest.mock import AsyncMock, MagicMock, patch

from quads.config import Config
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import BaseDao
from quads.server.dao.cloud import CloudDao
from quads.server.models import db
from tests.cli.config import NetcatStub
from tests.cli.test_base import TestBase


class TestNotify(TestBase):
    @patch("quads.tools.notify.get_chat_dispatcher")
    @patch("quads.tools.notify.get_email_dispatcher")
    def test_notify_not_validated(self, mock_email_dispatcher, mock_chat_dispatcher):
        Config.__setattr__("foreman_unavailable", True)

        # Mock email dispatcher
        email_disp = AsyncMock()
        email_disp.send_mail = AsyncMock()
        mock_email_dispatcher.return_value = email_disp

        # Mock chat dispatcher
        chat_disp = AsyncMock()
        chat_disp.send_message = AsyncMock()
        mock_chat_dispatcher.return_value = chat_disp

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

    @patch("quads.tools.notify.get_dayzero_dispatcher")
    @patch("quads.tools.notify.get_chat_dispatcher")
    @patch("quads.tools.notify.get_email_dispatcher")
    def test_notify_validated(self, mock_email_dispatcher, mock_chat_dispatcher, mock_dayzero_dispatcher):
        Config.__setattr__("foreman_unavailable", True)
        Config.__setattr__("webhook_notify", True)

        # Mock email dispatcher
        email_disp = AsyncMock()
        email_disp.send_mail = AsyncMock()
        mock_email_dispatcher.return_value = email_disp

        # Mock chat dispatcher
        chat_disp = AsyncMock()
        chat_disp.send_message = AsyncMock()
        mock_chat_dispatcher.return_value = chat_disp

        # Mock dayzero dispatcher
        dayzero_disp = MagicMock()
        dayzero_disp.execute = MagicMock()
        mock_dayzero_dispatcher.return_value = dayzero_disp

        cloud = CloudDao.get_cloud(name="cloud99")
        ass = AssignmentDao.get_active_cloud_assignment(cloud=cloud)
        setattr(ass, "validated", True)
        BaseDao.safe_commit()

        self.quads_cli_call("notify")
        db.session.refresh(ass)
        assert ass.notification.pre_initial is True
        assert ass.notification.initial is True
        assert self._caplog.messages[1:] == [
            "=============== Initial Message",
            "Notifications sent out.",
        ]
