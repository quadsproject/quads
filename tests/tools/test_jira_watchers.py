import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from quads.config import Config
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.cloud import CloudDao
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.dao.vlan import VlanDao
from quads.tools.external.jira import JiraException
from quads.tools.jira_watchers import main
from tests.cli.config import CLOUD, DEFAULT_CLOUD, HOST1


class TestJiraWatchers(object):
    @patch("quads.tools.external.postman.SMTP")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_main(self, mock_get, mock_post, mock_put, mock_smtp):
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
        resp = AsyncMock()
        resp.json.side_effect = [
            {
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
            },
            {"issues": [{"statusCategory": 4, "name": "unitest", "key": "2"}]},
            {"watchers": [{"key": "1"}]},
        ]
        mock_get.return_value.__aenter__.return_value = resp

        post_resp = AsyncMock()
        post_resp.status = 200
        post_resp.json.return_value = {}
        mock_post.return_value.__aenter__.return_value = post_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        mock_put.return_value.__aenter__.return_value = put_resp

        Config.jira_url = "https://mock_jira.com"
        Config.jira_auth = "token"
        Config.jira_token = "token"
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 0

    @patch("quads.tools.external.postman.SMTP")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_main_post_fail(self, mock_get, mock_post, mock_put, mock_smtp):
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
        resp = AsyncMock()
        resp.json.side_effect = [
            {
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
            },
            {"issues": [{"statusCategory": 4, "name": "unitest", "key": "2"}]},
            {"watchers": [{"key": "1"}]},
        ]
        mock_get.return_value.__aenter__.return_value = resp

        post_resp = AsyncMock()
        post_resp.status = 404
        post_resp.json.return_value = {}
        mock_post.return_value.__aenter__.return_value = post_resp

        put_resp = AsyncMock()
        put_resp.status = 404
        put_resp.json.return_value = {}
        mock_put.return_value.__aenter__.return_value = put_resp

        Config.jira_url = "https://mock_jira.com"
        Config.jira_auth = "token"
        Config.jira_token = "token"
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 0

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_main_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.side_effect = [{"issues": []}, {"issues": []}]
        mock_get.return_value.__aenter__.return_value = resp
        Config.jira_url = "https://mock_jira.com"
        Config.jira_auth = "token"
        Config.jira_token = "token"
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 0

    @patch("quads.tools.jira_watchers.Jira")
    @pytest.mark.asyncio
    async def test_main_error(self, mock_jira_class):
        mock_jira_class.side_effect = JiraException("Jira Exception")
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 1
