from unittest.mock import AsyncMock, patch
from aiohttp import BasicAuth

import pytest

from quads.config import Config
from quads.tools.external.jira import Jira, JiraException


class TestJira(object):
    url = "https://jira_test.con"
    username = "jira"
    password = "password"
    loop = AsyncMock()
    semaphore = AsyncMock()

    def test_class_object_parameters(self):
        jira = Jira(url=self.url, username=self.username, password=self.password)
        assert jira.url == self.url
        assert jira.password == self.password

    def test_class_object_parameters_with_loop(self):
        Config.jira_auth = "token"
        Config.jira_token = "token"
        jira = Jira(url=self.url, loop=self.loop, semaphore=self.semaphore)
        assert jira.headers == {
            "Authorization": "Bearer: token",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        assert jira.auth is None

    def test_class_object_parameters_basic_auth(self):
        Config.jira_auth = "basic"
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            loop=self.loop,
            semaphore=self.semaphore,
        )

        assert isinstance(jira.auth, BasicAuth)
        assert jira.auth.login == self.username
        assert jira.auth.password == self.password

        assert jira.headers == {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def test_class_object_parameters_raise_error(self):
        with pytest.raises(JiraException):
            Config.jira_auth = "basic"
            Jira(url=self.url, loop=self.loop, semaphore=self.semaphore)

    def test_class_object_token_error(self):
        with pytest.raises(JiraException):
            Config.jira_auth = "token"
            Config.jira_token = ""
            Jira(url=self.url, loop=self.loop, semaphore=self.semaphore)

    def test_exit_closed(self):
        Config.jira_auth = "basic"
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        jira.__exit__()
        assert jira.loop.is_closed()

    def test_exit_running(self):
        Config.jira_auth = "basic"
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        jira.new_loop = False
        jira.__exit__()
        assert not jira.loop.is_closed()

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_request(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {"test": "mock_result"}
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_request("/test")
        assert response == {"test": "mock_result"}

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_request_exception(self, mock_get):
        mock_get.side_effect = Exception("Unittest Exception Raised")
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_request("/test")
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_request_response_404(self, mock_get):
        resp = AsyncMock()
        resp.status = 404
        resp.json.return_value = {"test": "mock_result"}
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_request("/test")
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_request(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.post_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_request_exception(self, mock_post):
        mock_post.side_effect = Exception("Unittest Exception Raised")
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.post_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_request_response_404(self, mock_post):
        resp = AsyncMock()
        resp.status = 404
        resp.json.return_value = {"test": "mock_result"}
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        result, response = await jira.post_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not result

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_request_response_false(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        result, response = await jira.post_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not result

    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_request(self, mock_put):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_put.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.put_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_request_exception(self, mock_put):
        mock_put.side_effect = Exception("Unittest Exception Raised")
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.put_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_request_response_404(self, mock_put):
        resp = AsyncMock()
        resp.status = 404
        resp.json.return_value = {"test": "mock_result"}
        mock_put.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.put_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_request_response_false(self, mock_put):
        resp = AsyncMock()
        resp.json.return_value = {}
        mock_put.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.put_request(
            endpoint="/test", payload={"test": "mock_result"}
        )
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_add_watcher(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.add_watcher(ticket=123, watcher="unitest@gmail.com")
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_add_label(self, mock_put):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_put.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.add_label(ticket=123, label="unitest")
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_comment(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.post_comment(ticket=123, comment="This is unitest")
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_transition(self, mock_post):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 200
        mock_post.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.post_transition(ticket=123, transition="Closed")
        assert response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_transitions(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {"transitions": ["Closed"]}
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_transitions(ticket=123)
        assert response == ["Closed"]

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_transitions_fail(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 404
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_transitions(ticket=123)
        assert len(response) == 0

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_transitions_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {"transitions": []}
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_transitions(ticket=123)
        assert len(response) == 0

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_project_transitions(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [{"statuses": ["New", "Open"]}]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_project_transitions()
        assert response == ["New", "Open"]

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_project_transitions_fail(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 404
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_project_transitions()
        assert len(response) == 0

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_project_transitions_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [{"statuses": []}]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_project_transitions()
        assert len(response) == 0

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_transition_id(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [
            {"statuses": [{"name": "Closed", "id": "2"}, {"name": "New", "id": "1"}]}
        ]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_transition_id(status="New")
        assert response == "1"

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_transition_id_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [{"statuses": []}]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_transition_id(status="New")
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_ticket(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {"key": "1"}
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_ticket(ticket="1")
        assert response == {"key": "1"}

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_ticket_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 404
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_ticket(ticket="1")
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_watchers(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {"watchers": ["unittest@gmail.com"]}
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_watchers(ticket="1")
        assert response == {"watchers": ["unittest@gmail.com"]}

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_watchers_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 404
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_watchers(ticket="1")
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_all_pending_tickets(self, mock_get):
        resp = AsyncMock()
        resp.json.side_effect = [
            [
                {
                    "statuses": [
                        {"name": "In Progress", "id": "1"},
                        {"name": "Closed", "id": "2"},
                    ]
                }
            ],
            [{"name": "unitest", "key": "1"}],
        ]
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_all_pending_tickets()
        assert response == [{"name": "unitest", "key": "1"}]

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_all_pending_tickets_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.side_effect = [
            [
                {
                    "statuses": [
                        {"name": "In Progress", "id": "1"},
                        {"name": "Closed", "id": "2"},
                    ]
                }
            ]
        ]
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_all_pending_tickets()
        assert not response

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_pending_tickets(self, mock_get):
        resp = AsyncMock()
        resp.json.side_effect = [
            {
                "issues": [
                    {
                        "name": "unitest",
                        "key": "1",
                        "statusCategory": 4,
                        "labels": "EXPANSION",
                    }
                ]
            },
            {
                "issues": [
                    {
                        "statusCategory": 4,
                        "labels": "EXTENSION",
                        "name": "unitest",
                        "key": "1",
                    }
                ]
            },
        ]
        mock_get.return_value.__aenter__.return_value = resp

        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.get_pending_tickets()
        assert response == {
            "issues": [
                {
                    "name": "unitest",
                    "key": "1",
                    "statusCategory": 4,
                    "labels": "EXPANSION",
                },
                {
                    "statusCategory": 4,
                    "labels": "EXTENSION",
                    "name": "unitest",
                    "key": "1",
                },
            ]
        }

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_search_tickets(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [{"name": "unitest", "key": "1"}]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.search_tickets()
        assert response == [{"name": "unitest", "key": "1"}]

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_search_tickets_query(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = [{"name": "unitest", "key": "1"}]
        resp.status = 200
        mock_get.return_value.__aenter__.return_value = resp
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.search_tickets(query={"key": "1"})
        assert response == [{"name": "unitest", "key": "1"}]

    @patch("quads.tools.external.jira.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_search_tickets_empty(self, mock_get):
        resp = AsyncMock()
        resp.json.return_value = {}
        resp.status = 404
        mock_get.return_value.__aenter__.return_value = resp
        jira = Jira(
            url=self.url,
            username=self.username,
            password=self.password,
            semaphore=self.semaphore,
        )
        response = await jira.search_tickets()
        assert not response
