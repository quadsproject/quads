from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from quads.tools.jira_watchers import main
from tests.cli.config import CLOUD, DEFAULT_CLOUD, HOST1


class TestJiraWatchers(object):
    @patch("quads.tools.jira_watchers.get_email_dispatcher")
    @patch("quads.tools.jira_watchers.PluginManager")
    @pytest.mark.asyncio
    async def test_main(self, mock_pm_class, mock_get_email):
        today = datetime.now()
        tomorrow = today + timedelta(weeks=2)
        cloud_name = CLOUD
        host_name = HOST1
        host = HostDao.get_host(host_name)
        cloud = CloudDao.get_cloud(cloud_name)
        vlan = VlanDao.create_vlan("192.168.1.1", 122, "192.168.1.1/22", "255.255.255.255", 1)
        assignment = AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], cloud.name, vlan.vlan_id)
        ScheduleDao.create_schedule(
            today.strftime("%Y-%m-%d %H:%M"),
            tomorrow.strftime("%Y-%m-%d %H:%M"),
            assignment,
            host,
        )

        mock_jira = AsyncMock()
        mock_jira.get_pending_tickets.return_value = {
            "issues": [
                {
                    "name": "unitest",
                    "key": "1",
                    "fields": {
                        "description": f"Submitted by: unittest@gmail.com\nCloud to extend: {cloud_name}\nJustification: Need "
                        "more time to make unittests",
                        "parent": {"key": "5"},
                        "labels": ["EXTENSION"],
                    },
                },
                {
                    "name": "unitest3",
                    "key": "4",
                    "fields": {
                        "description": f"Submitted by: unittest@gmail.com\nCloud to extend: {DEFAULT_CLOUD}\nJustification: Need "
                        "more time to make unittests",
                        "labels": ["EXPANSION"],
                    },
                },
                {
                    "name": "unitest3",
                    "key": "4",
                    "fields": {
                        "description": "Submitted by: unittest@gmail.com\n",
                        "labels": ["EXPANSION"],
                    },
                },
            ]
        }
        mock_jira.add_label.return_value = True
        mock_jira.get_watchers.return_value = {"watchers": [{"key": "1"}]}
        mock_jira.add_watcher.return_value = True

        mock_plugin = MagicMock()
        mock_plugin.jira = mock_jira

        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = mock_plugin
        mock_pm_class.return_value = mock_pm

        mock_email = AsyncMock()
        mock_get_email.return_value = mock_email

        response = await main()
        assert response == 0

    @patch("quads.tools.jira_watchers.get_email_dispatcher")
    @patch("quads.tools.jira_watchers.PluginManager")
    @pytest.mark.asyncio
    async def test_main_post_fail(self, mock_pm_class, mock_get_email):
        today = datetime.now()
        tomorrow = today + timedelta(days=1)
        cloud_name = CLOUD
        host_name = HOST1
        host = HostDao.get_host(host_name)
        cloud = CloudDao.get_cloud(cloud_name)
        vlan = VlanDao.create_vlan("192.168.1.1", 122, "192.168.1.1/22", "255.255.255.255", 1)
        assignment = AssignmentDao.create_assignment("test", "test", "1234", 0, False, [""], cloud.name, vlan.vlan_id)
        ScheduleDao.create_schedule(
            today.strftime("%Y-%m-%d %H:%M"),
            tomorrow.strftime("%Y-%m-%d %H:%M"),
            assignment,
            host,
        )

        mock_jira = AsyncMock()
        mock_jira.get_pending_tickets.return_value = {
            "issues": [
                {
                    "name": "unitest",
                    "key": "1",
                    "fields": {
                        "description": f"Submitted by: unittest@gmail.com\nCloud to extend: {cloud_name}\nJustification: Need "
                        "more time to make unittests",
                        "parent": {"key": "5"},
                        "labels": ["EXTENSION"],
                    },
                },
                {
                    "name": "unitest3",
                    "key": "4",
                    "fields": {
                        "description": f"Submitted by: unittest@gmail.com\nCloud to extend: {DEFAULT_CLOUD}\nJustification: Need "
                        "more time to make unittests",
                        "labels": ["EXPANSION"],
                    },
                },
                {
                    "name": "unitest3",
                    "key": "4",
                    "fields": {
                        "description": "Submitted by: unittest@gmail.com\n",
                        "labels": ["EXPANSION"],
                    },
                },
            ]
        }
        mock_jira.add_label.return_value = False
        mock_jira.get_watchers.return_value = {"watchers": [{"key": "1"}]}
        mock_jira.add_watcher.return_value = False

        mock_plugin = MagicMock()
        mock_plugin.jira = mock_jira

        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = mock_plugin
        mock_pm_class.return_value = mock_pm

        mock_email = AsyncMock()
        mock_get_email.return_value = mock_email

        response = await main()
        assert response == 0

    @patch("quads.tools.jira_watchers.PluginManager")
    @pytest.mark.asyncio
    async def test_main_empty(self, mock_pm_class):
        mock_jira = AsyncMock()
        mock_jira.get_pending_tickets.return_value = {"issues": []}

        mock_plugin = MagicMock()
        mock_plugin.jira = mock_jira

        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = mock_plugin
        mock_pm_class.return_value = mock_pm

        response = await main()
        assert response == 0

    @patch("quads.tools.jira_watchers.PluginManager")
    @pytest.mark.asyncio
    async def test_main_error(self, mock_pm_class):
        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = None
        mock_pm_class.return_value = mock_pm

        response = await main()
        assert response == 1
