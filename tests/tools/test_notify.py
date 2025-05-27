import asyncio
from unittest.mock import patch, MagicMock
from tests.cli.config import NetcatStub

from quads.tools.notify import (
    create_message,
    create_future_initial_message,
    create_future_message,
    create_initial_message,
)
from tests.config import (
    INITIAL_MESSAGE,
    CC_USERS,
    OWNER,
    INITIAL_SUBJECT,
    SUBJECT,
    MESSAGE,
    FUTURE_INITIAL_SUBJECT,
    FUTURE_INITIAL_MESSAGE,
    FUTURE_SUBJECT,
    FUTURE_MESSAGE,
    POST_TEXT,
)


def run_async(func):
    return asyncio.run(func)


class TestNotify:
    @patch("quads.tools.notify.Netcat", NetcatStub)
    @patch("quads.tools.notify.Postman")
    @patch("quads.tools.notify.requests.post")
    def test_create_initial_message(self, mock_post, mock_postman):
        mock_post.return_value.status_code = 200
        # Setup
        cloud = "cloud1"
        cloud_info = "cloud_info1"
        ticket = "ticket1"
        cc = ["cc1", "cc2"]

        # Call the function
        run_async(create_initial_message(OWNER, cloud, cloud_info, ticket, cc))

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            INITIAL_SUBJECT,
            OWNER,
            CC_USERS + ["cc1@example.com", "cc2@example.com"],
            INITIAL_MESSAGE,
        )
        mock_post.assert_called_once_with(
            "https://chat.example.com/v1/spaces/AAABBBCCC",
            json={
                "text": POST_TEXT,
            },
            headers={"Content-Type": "application/json"},
        )

    @patch("quads.tools.notify.Postman")
    def test_create_message(self, mock_postman):
        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1")
        day = 1
        cloud_info = "cloud_info1"
        host_list_expire = ["host1", "host2"]

        # Call the function
        create_message(cloud, assignment_obj, day, cloud_info, host_list_expire)

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            SUBJECT,
            OWNER,
            CC_USERS,
            MESSAGE,
        )

    @patch("quads.tools.notify.Postman")
    def test_create_future_initial_message(self, mock_postman):
        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1", is_self_schedule=False)
        cloud_info = "cloud_info1"

        # Call the function
        create_future_initial_message(cloud, assignment_obj, cloud_info)

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            FUTURE_INITIAL_SUBJECT,
            OWNER,
            CC_USERS,
            FUTURE_INITIAL_MESSAGE,
        )

    @patch("quads.tools.notify.Postman")
    def test_create_future_message(self, mock_postman):
        # Setup
        cloud = "cloud1"
        assignment_obj = MagicMock(ticket="ticket1", owner="owner1")
        future_days = 1
        cloud_info = "cloud_info1"
        host_list_expire = ["host1", "host2"]

        # Call the function
        create_future_message(cloud, assignment_obj, future_days, cloud_info, host_list_expire)

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            FUTURE_SUBJECT,
            OWNER,
            CC_USERS,
            FUTURE_MESSAGE,
        )
