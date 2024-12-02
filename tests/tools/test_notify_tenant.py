import asyncio
import tempfile
import os
from unittest.mock import patch, MagicMock
from tests.tools.test_base import TestBase

from quads.tools.notify_tenant import (
    verify_argparse as notify_tenant_verify_argparse,
    determine_action as notify_tenant_determine_action,
    send_message as notify_tenant_send_message,
    main as notify_tenant_main,
)


def run_async(func):
    return asyncio.get_event_loop().run_until_complete(func)


class FakeArgs(object):
    def __init__(self, subject, message, racks, clouds, all):
        self.subject = subject
        self.message = message
        self.racks = racks
        self.clouds = clouds
        self.all = False


class TestNotifyTenant:
    tempfile = tempfile.NamedTemporaryFile(delete=False)
    fake_args = FakeArgs("Test Subject", tempfile.name, None, "cloud01", False)

    @patch("quads.tools.notify_tenant.Postman")
    def test_notify_tenant_send_message(self, mock_postman):
        # Setup
        fp = open(tempfile.name, "w")
        fp.write("Hello world.\n")
        fp.close()
        owner = "quads_user"
        cc = ["cc1", "cc2"]
        ticket = "12345"
        description = "cloud description"
        cloud_name = "cloud01"

        # Call the function
        run_async(notify_tenant_send_message(self.fake_args, owner, cc, ticket, description, cloud_name))

        # Assert that Postman was called with the correct arguments
        mock_postman.assert_called_once_with(
            self.fake_args.subject,
            owner,
            ["cc1@example.com", "cc2@example.com"],
            tempfile.name,
        )

        # remove tempfile
        os.remove(tempfile.name)

    @patch("quads.tools.notify_tenant.QuadsApi")
    def test_notify_tenant_determine_action(self, fake_args, mock_quads_api):
        mock_quads_api.get_cloud.return_value = MagicMock()
        mock_quads_api.get_clouds.return_value = MagicMock()
        mock_quads_api.filter_hosts.return_value = MagicMock()
        mock_quads_api.filter_assignments.return_value = MagicMock()
        notify_tenant_determine_action(self.fake_args)
