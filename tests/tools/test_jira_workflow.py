import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from quads.config import Config
from quads.tools.external.jira import JiraException
from quads.tools.jira_workflow import main
from tests.cli.config import CLOUD, DEFAULT_CLOUD


class TestJiraWorkflow(object):
    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_main(self, mock_get, mock_post):
        cloud_name = CLOUD
        resp = AsyncMock()
        resp.json.side_effect = [
            [
                {
                    "statuses": [
                        {"name": "In Progress", "id": "1"},
                        {"name": "In Progress", "id": "2"},
                    ]
                }
            ],
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
                            "status": "In Progress",
                        },
                    },
                    {
                        "name": "unitest3",
                        "key": "4",
                        "fields": {
                            "description": f"Submitted by: unittest@gmail.com\nCloud to extend: {DEFAULT_CLOUD}\nJustification: Need "
                            "more time to make unittests",
                            "labels": ["EXPANSION"],
                            "status": "In Progress",
                        },
                    },
                    {
                        "name": "unitest3",
                        "key": "5",
                        "fields": {
                            "description": "Submitted by: unittest@gmail.com\n",
                            "labels": ["EXPANSION"],
                        },
                    },
                ]
            },
            {"transitions": [{"name": "done", "id": "1"}]},
            {"transitions": [{"name": "New", "id": "2"}]},
        ]
        mock_get.return_value.__aenter__.return_value = resp

        post_resp = AsyncMock()
        post_resp.status = 200
        post_resp.json.return_value = {}
        mock_post.return_value.__aenter__.return_value = post_resp

        Config.jira_url = "https://mock_jira.com"
        Config.jira_auth = "token"
        Config.jira_token = "token"
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 0

    @patch("quads.tools.jira_workflow.Jira")
    @pytest.mark.asyncio
    async def test_main_error(self, mock_jira_class):
        mock_jira_class.side_effect = JiraException("Jira Exception")
        loop = asyncio.new_event_loop()
        response = await main(_loop=loop)
        assert response == 1
