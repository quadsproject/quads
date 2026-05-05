from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.tools.jira_workflow import main
from tests.cli.config import CLOUD, DEFAULT_CLOUD


class TestJiraWorkflow(object):
    @patch("quads.tools.jira_workflow.PluginManager")
    @pytest.mark.asyncio
    async def test_main(self, mock_pm_class):
        cloud_name = CLOUD

        mock_jira = AsyncMock()
        mock_jira.get_all_pending_tickets.return_value = {
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
        }
        mock_jira.get_transitions.side_effect = [
            [{"name": "done", "id": "1"}],
            [{"name": "New", "id": "2"}],
        ]
        mock_jira.post_transition.return_value = True

        mock_plugin = MagicMock()
        mock_plugin.jira = mock_jira

        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = mock_plugin
        mock_pm_class.return_value = mock_pm

        response = await main()
        assert response == 0

    @patch("quads.tools.jira_workflow.PluginManager")
    @pytest.mark.asyncio
    async def test_main_error(self, mock_pm_class):
        mock_pm = MagicMock()
        mock_pm.get_plugin.return_value = None
        mock_pm_class.return_value = mock_pm

        response = await main()
        assert response == 1
