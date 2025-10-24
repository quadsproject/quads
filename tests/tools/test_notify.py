import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from quads.tools.notify import (
    create_future_initial_message,
    create_future_message,
    create_initial_message,
    create_message,
)
from tests.config import (
    OWNER,
)


class TestNotify:
    @patch("quads.tools.notify.get_chat_dispatcher")
    @patch("quads.tools.notify.get_email_dispatcher")
    @patch("quads.tools.notify.PluginManager")
    def test_create_initial_message(self, mock_plugin_manager, mock_email_dispatcher, mock_chat_dispatcher):
        # Setup mocks
        mock_email_disp = MagicMock()
        mock_email_disp.send_mail = AsyncMock(return_value={"email": True})
        mock_email_dispatcher.return_value = mock_email_disp

        mock_chat_disp = MagicMock()
        mock_chat_disp.send_message = AsyncMock(return_value={"gchat": True})
        mock_chat_dispatcher.return_value = mock_chat_disp

        # Setup
        cloud = "cloud1"
        cloud_info = "cloud_info1"
        ticket = "ticket1"
        cc = ["cc1", "cc2"]

        # Call the function
        asyncio.run(create_initial_message(OWNER, cloud, cloud_info, ticket, cc))

        # Assert that email dispatcher was called
        mock_email_disp.send_mail.assert_called_once()
        call_kwargs = mock_email_disp.send_mail.call_args[1]
        assert "New QUADS Assignment Allocated" in call_kwargs["subject"]
        assert cloud in call_kwargs["subject"]

        # Assert that chat dispatcher was called
        mock_chat_disp.send_message.assert_called_once()

    @patch("quads.tools.notify.get_email_dispatcher")
    @patch("quads.tools.notify.PluginManager")
    def test_create_message(self, mock_plugin_manager, mock_email_dispatcher):
        # Setup mocks
        mock_email_disp = MagicMock()
        mock_email_disp.send_mail_sync = MagicMock(return_value={"email": True})
        mock_email_dispatcher.return_value = mock_email_disp

        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1", ccuser=[])
        day = 1
        cloud_info = "cloud_info1"
        host_list_expire = ["host1", "host2"]

        # Call the function
        create_message(cloud, assignment_obj, day, cloud_info, host_list_expire)

        # Assert that email dispatcher was called
        mock_email_disp.send_mail_sync.assert_called_once()
        call_kwargs = mock_email_disp.send_mail_sync.call_args[1]
        assert "QUADS upcoming expiration" in call_kwargs["subject"]
        assert cloud in call_kwargs["subject"]

    @patch("quads.tools.notify.get_email_dispatcher")
    @patch("quads.tools.notify.PluginManager")
    def test_create_future_initial_message(self, mock_plugin_manager, mock_email_dispatcher):
        # Setup mocks
        mock_email_disp = MagicMock()
        mock_email_disp.send_mail_sync = MagicMock(return_value={"email": True})
        mock_email_dispatcher.return_value = mock_email_disp

        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1", is_self_schedule=False, ccuser=[])
        cloud_info = "cloud_info1"

        # Call the function
        create_future_initial_message(cloud, assignment_obj, cloud_info)

        # Assert that email dispatcher was called
        mock_email_disp.send_mail_sync.assert_called_once()
        call_kwargs = mock_email_disp.send_mail_sync.call_args[1]
        assert "New QUADS Assignment Defined for the Future" in call_kwargs["subject"]
        assert cloud in call_kwargs["subject"]

    @patch("quads.tools.notify.get_email_dispatcher")
    @patch("quads.tools.notify.PluginManager")
    def test_create_future_message(self, mock_plugin_manager, mock_email_dispatcher):
        # Setup mocks
        mock_email_disp = MagicMock()
        mock_email_disp.send_mail_sync = MagicMock(return_value={"email": True})
        mock_email_dispatcher.return_value = mock_email_disp

        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1", ccuser=[])
        future_days = 1
        cloud_info = "cloud_info1"
        host_list_expire = ["host1", "host2"]

        # Call the function
        create_future_message(cloud, assignment_obj, future_days, cloud_info, host_list_expire)

        # Assert that email dispatcher was called
        mock_email_disp.send_mail_sync.assert_called_once()
        call_kwargs = mock_email_disp.send_mail_sync.call_args[1]
        assert "QUADS upcoming assignment notification" in call_kwargs["subject"]
        assert cloud in call_kwargs["subject"]
