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

    @patch("quads.tools.notify_tenant.get_email_dispatcher")
    @patch("quads.tools.notify_tenant.PluginManager")
    def test_notify_tenant_send_message(self, mock_plugin_manager, mock_email_dispatcher, setup):
        # Setup mocks
        mock_email_disp = MagicMock()
        mock_email_disp.send_mail_sync = MagicMock(return_value={"email": True})
        mock_email_dispatcher.return_value = mock_email_disp

        owner = "quads_user"
        cc = ["cc1", "cc2"]
        ticket = "12345"
        description = "cloud description"
        cloud_name = "cloud01"
        content, fake_args = setup

        # Call the function
        notify_tenant_send_message(fake_args, owner, cc, ticket, description, cloud_name)

        # Assert that email dispatcher was called
        mock_email_disp.send_mail_sync.assert_called_once()
        call_kwargs = mock_email_disp.send_mail_sync.call_args[1]
        assert call_kwargs["subject"] == f"INFO: [{cloud_name}] {fake_args.subject}"
        assert content in call_kwargs["content"]

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
