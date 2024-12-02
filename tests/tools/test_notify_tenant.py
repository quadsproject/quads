import asyncio
import tempfile
import pytest
import os
from unittest.mock import patch, AsyncMock, MagicMock
from tests.tools.test_base import TestBase

from quads.tools.notify_tenant import (
    verify_argparse as notify_tenant_verify_argparse,
    determine_action as notify_tenant_determine_action,
    send_message as notify_tenant_send_message,
    post_message as notify_tenant_post_message,
    main as notify_tenant_main,
)


class FakeArgs(object):
    def __init__(self, subject, message, rack, cloud, all):
        self.subject = subject
        self.message = message
        self.rack = rack
        self.cloud = cloud
        self.all = False


class TestNotifyTenant:
    f = tempfile.NamedTemporaryFile(delete=False)
    fake_args = FakeArgs("Test Subject", f.name, None, "cloud01", False)
    content = "Hello world."

    @patch("quads.tools.notify_tenant.Postman")
    def test_notify_tenant_send_message(self, mock_postman):
        # Setup
        fp = open(self.f.name, "w")
        fp.write(self.content)
        fp.close()
        owner = "quads_user"
        cc = ["cc1", "cc2"]
        ticket = "12345"
        description = "cloud description"
        cloud_name = "cloud01"

        # Call the function
        notify_tenant_send_message(self.fake_args, owner, cc, ticket, description, cloud_name)

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            "INFO: [%s] %s" % (cloud_name, self.fake_args.subject),
            owner,
            [
                "someuser@example.com",
                "someuser@example.com",
                "someuser@example.com",
                "someuser@example.com",
                "cc1@example.com",
                "cc2@example.com",
            ],
            self.content,
        )

        # remove tempfile
        os.remove(self.f.name)

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    def test_notify_tenant_post_message(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp

    @patch("quads.tools.notify_tenant.QuadsApi")
    def test_notify_tenant_determine_action(self, fake_args):
        notify_tenant_determine_action(self.fake_args)
