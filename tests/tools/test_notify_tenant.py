import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.tools.notify_tenant import determine_action as notify_tenant_determine_action
from quads.tools.notify_tenant import post_message as notify_tenant_post_message
from quads.tools.notify_tenant import send_message as notify_tenant_send_message
from quads.tools.notify_tenant import verify_argparse as notify_tenant_verify_argparse
from tests.tools.test_base import TestBase


class FakeArgs(object):
    def __init__(self, subject, message, rack, cloud, all):
        self.subject = subject
        self.message = message
        self.rack = rack
        self.cloud = cloud
        self.all = False


class TestNotifyTenant(TestBase):

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, request):
        content = "Hello world."
        f = tempfile.NamedTemporaryFile(delete=False)
        with open(f.name, "w") as fp:
            fp.write(content)

        fake_args = FakeArgs("Test Subject", f.name, None, "cloud01", False)

        yield content, fake_args

        # remove tempfile
        os.remove(f.name)

    @patch("quads.tools.notify_tenant.Postman")
    def test_notify_tenant_send_message(self, mock_postman, setup):
        owner = "quads_user"
        cc = ["cc1", "cc2"]
        ticket = "12345"
        description = "cloud description"
        cloud_name = "cloud01"
        content, fake_args = setup

        # Call the function
        notify_tenant_send_message(fake_args, owner, cc, ticket, description, cloud_name)

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            "INFO: [%s] %s" % (cloud_name, fake_args.subject),
            owner,
            [
                "someuser@example.com",
                "someuser@example.com",
                "someuser@example.com",
                "someuser@example.com",
                "cc1@example.com",
                "cc2@example.com",
            ],
            content,
        )

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @patch("quads.tools.notify_tenant.QuadsApi.filter_assignments")
    @pytest.mark.asyncio
    def test_notify_tenant_post_message(self, mock_ass, mock_post, setup):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp
        ticket = "12345"
        mock_ass.return_value = MagicMock(ticket=ticket, status=200)
        description = "cloud description"
        cloud_name = "cloud01"
        _, fake_args = setup
        result = notify_tenant_post_message(fake_args, ticket, description, cloud_name)
        assert result is True

    @patch("quads.tools.notify_tenant.QuadsApi")
    def test_notify_tenant_determine_action(self, mock_api, caplog, setup):
        _, fake_args = setup
        mock_api.get_cloud.return_value = MagicMock()
        mock_api.get_clouds.return_value = MagicMock()
        mock_api.filter_hosts.return_value = MagicMock()
        mock_api.filter_assignments.return_value = MagicMock()
        results = notify_tenant_determine_action(fake_args)

        assert isinstance(results, list)
        assert "Skipping notification for cloud01. This is used for available hosts." in caplog.text
