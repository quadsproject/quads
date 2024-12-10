#!/usr/bin/env python3
import asyncio
from unittest.mock import patch, AsyncMock

import pytest

from quads.tools.external.foreman import Foreman


class TestForeman(object):
    @pytest.mark.asyncio
    async def test_initialize_foreman_with_valid_parameters(self):
        foreman = Foreman("https://example.com", "username", "password")

        assert foreman.url == "https://example.com"
        assert foreman.username == "username"
        assert foreman.password == "password"
        semaphore = AsyncMock()
        Foreman(
            "https://example.com",
            "username",
            "password",
            semaphore=semaphore,
        )

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get(self, session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}
        session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.get("/test")
        assert response == {"results": [{"name": "host.example.com"}]}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_obj_dict_empty(self, session):
        resp = AsyncMock()
        resp.json.return_value = {"name": "host.example.com"}
        session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.get_obj_dict(endpoint="/test_get_obj_dict")
        assert response == {}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_obj_dict(self, session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}
        session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.get_obj_dict(endpoint="/test_get_obj_dict")
        assert response == {"host.example.com": {"name": "host.example.com"}}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_set_host_parameter_true(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.set_host_parameter(
            host_name="host.example.com", name="host.example.com", value="host1"
        )
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_set_host_parameter_false(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 500
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.set_host_parameter(
            host_name="host.example.com", name="host.example.com", value="host1"
        )
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_host_parameter_raise_exception(self, put_session):
        put_session.side_effect = Exception("Simulated error")
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.put_host_parameter(host_id="host1", parameter_id="host1", value="host1")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_host_parameter(self, post_session):
        post_resp = AsyncMock()
        post_resp.status = 200
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.post_host_parameter(host_id="host1", name="host.example.com", value="host1")
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_host_parameter_false(self, post_session):
        post_resp = AsyncMock()
        post_resp.status = 500
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.post_host_parameter(host_id="host1", name="host.example.com", value="host1")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_host_parameter_raise_exception(self, post_session):
        post_session.side_effect = Exception("Simulated error")
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.post_host_parameter(host_id="host1", name="host.example.com", value="host1")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_update_user_password(self, put_session):
        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.update_user_password(login="user1", password="password")
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_update_user_password_raise_exception(self, put_session):
        put_session.side_effect = Exception("Simulated error")
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.update_user_password(login="user1", password="password")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_update_user_password_false(self, put_session):
        put_resp = AsyncMock()
        put_resp.status = 500
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.update_user_password(login="user1", password="password")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_elements_raise_exception(self, put_session):
        put_session.side_effect = Exception("Simulated error")
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.put_elements(element_name="test", element_id="test1", params="test")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_put_elements_false(self, put_session):
        put_resp = AsyncMock()
        put_resp.status = 500
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.put_elements(element_name="test", element_id="test1", params="test")
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_with_exception_err(self, session):
        session.return_value.__aenter__.side_effect = Exception("Simulated exception")

        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.get("/test")
        assert response == {}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_all_hosts(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}

        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        all_hosts = await foreman.get_all_hosts()

        assert all_hosts == {"host.example.com": {"name": "host.example.com"}}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_broken_hosts(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}

        session_mock.return_value.__aenter__.return_value = resp

        # Create the Foreman object with mocked session
        foreman = Foreman("https://example.com", "username", "password")
        all_hosts = await foreman.get_broken_hosts()

        assert all_hosts == {"host.example.com": {"name": "host.example.com"}}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_build_hosts(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}

        session_mock.return_value.__aenter__.return_value = resp

        # Create the Foreman object with mocked session
        foreman = Foreman("https://example.com", "username", "password")
        all_hosts = await foreman.get_build_hosts()

        assert all_hosts == {"host.example.com": {"name": "host.example.com"}}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_parametrized(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com"}]}

        session_mock.return_value.__aenter__.return_value = resp

        # Create the Foreman object with mocked session
        foreman = Foreman("https://example.com", "username", "password")
        all_hosts = await foreman.get_parametrized("build", True)

        assert all_hosts == {"host.example.com": {"name": "host.example.com"}}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_id(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}

        session_mock.return_value.__aenter__.return_value = resp

        # Create the Foreman object with mocked session
        foreman = Foreman("https://example.com", "username", "password")
        all_hosts = await foreman.get_host_id("host.example.com")

        assert all_hosts == "host1"

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_parameter_id(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        parameter_id = await foreman.get_host_parameter_id(
            host_name="host.example.com", parameter_name="host.example.com"
        )
        assert parameter_id == "host1"

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_user_id(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"login": "unittest", "id": "mock1"}]}
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        user_id = await foreman.get_user_id(user_name="unittest")
        assert user_id == "mock1"

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_role_id(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "unittest-role", "id": "mock1-role"}]}
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        role_id = await foreman.get_role_id(role="unittest-role")
        assert role_id == "mock1-role"

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_param(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1", "value": "test-host"}]}
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        host_param = await foreman.get_host_param(host_name="host.example.com", param="host.example.com")
        assert host_param == {"result": "test-host"}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_build_status_true(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "host.example.com", "build_status": True}]}
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        build_status = await foreman.get_host_build_status(host_name="host.example.com")
        assert build_status

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_extraneous_interfaces_with_mgmt(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "mgmt",
                    "id": "host1",
                    "build_status": True,
                }
            ]
        }
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        extraneous_interfaces = await foreman.get_host_extraneous_interfaces(host_id="host1")
        assert extraneous_interfaces == []

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_extraneous_interfaces_with_mgmt_with_primary_false(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "mgmt",
                    "id": "host1",
                    "primary": False,
                }
            ]
        }
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        extraneous_interfaces = await foreman.get_host_extraneous_interfaces(host_id="host1")
        assert extraneous_interfaces == []

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_extraneous_interfaces_with_mgmt_with_primary_true(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "mgmt",
                    "id": "host1",
                    "primary": True,
                }
            ]
        }
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        extraneous_interfaces = await foreman.get_host_extraneous_interfaces(host_id="host1")
        assert extraneous_interfaces == []

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_extraneous_interfaces_without_mgmt_with_primary_false(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "other",
                    "id": "host1",
                    "primary": False,
                }
            ]
        }
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        extraneous_interfaces = await foreman.get_host_extraneous_interfaces(host_id="host1")
        assert extraneous_interfaces == [
            {
                "name": "host.example.com",
                "identifier": "other",
                "id": "host1",
                "primary": False,
            }
        ]

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_host_extraneous_interfaces_without_mgmt_with_primary_true(self, session_mock):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "other",
                    "id": "host1",
                    "primary": True,
                }
            ]
        }
        session_mock.return_value.__aenter__.return_value = resp

        foreman = Foreman("https://example.com", "username", "password")
        extraneous_interfaces = await foreman.get_host_extraneous_interfaces(host_id="host1")
        assert extraneous_interfaces == []

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_remove_extraneous_interfaces_without_semaphore(self, get_session_mock, caplog):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "other",
                    "id": "host1",
                    "primary": False,
                }
            ]
        }
        get_session_mock.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response_ok = await foreman.remove_extraneous_interfaces(host="host.example.com")
        assert not response_ok
        log_contents = caplog.text
        assert "There was something wrong with your request." in log_contents

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_remove_extraneous_interfaces_with_semaphore_status_code200(
            self, delete_session_mock, get_session_mock, caplog
    ):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "other",
                    "id": "host1",
                    "primary": False,
                }
            ]
        }
        get_session_mock.return_value.__aenter__.return_value = get_resp

        delete_resp = AsyncMock()
        delete_resp.status = 200
        delete_resp.json.return_value = {}
        delete_session_mock.return_value.__aenter__.return_value = delete_resp

        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response_ok = await foreman.remove_extraneous_interfaces(host="host.example.com")
        assert response_ok

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_remove_extraneous_interfaces_with_semaphore_status_code400(
            self, delete_session_mock, get_session_mock, caplog
    ):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {
                    "name": "host.example.com",
                    "identifier": "other",
                    "id": "host1",
                    "primary": False,
                }
            ]
        }
        get_session_mock.return_value.__aenter__.return_value = get_resp

        delete_resp = AsyncMock()
        delete_resp.status = 400
        delete_session_mock.return_value.__aenter__.return_value = delete_resp

        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response_ok = await foreman.remove_extraneous_interfaces(host="host.example.com")
        assert not response_ok

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_add_role(self, put_session, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"login": "unittest", "id": "mock1", "name": "unittest-role1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp

        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response_ok = await foreman.add_role(user_name="unittest", role="unittest-role1")
        print(response_ok)
        assert response_ok

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_remove_role(self, put_session, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"login": "unittest", "id": "mock1", "name": "unittest-role1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp

        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response_ok = await foreman.remove_role(user_name="unittest", role="unittest-role1")
        assert response_ok

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @pytest.mark.asyncio
    async def test_remove_role_not_exists(self, put_session, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"login": "unittest", "id": "mock1", "name": "unittest-role2"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_resp.json.return_value = {}
        put_session.return_value.__aenter__.return_value = put_resp

        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response_ok = await foreman.remove_role(user_name="unittest", role="unittest-role1")
        assert response_ok

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_user_roles(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"login": "unittest", "id": "mock1", "name": "unittest-role1"}]}
        get_session.return_value.__aenter__.return_value = get_resp
        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response = await foreman.get_user_roles(user_id="mock1")
        assert response == {
            "unittest-role1": {
                "login": "unittest",
                "id": "mock1",
                "name": "unittest-role1",
            }
        }

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_user_roles_remove_default(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {"login": "unittest", "id": "mock1", "name": "unittest-role1"},
                {"id": "mock1", "name": "Default role"},
            ]
        }
        get_session.return_value.__aenter__.return_value = get_resp
        foreman = Foreman("https://example.com", "username", "password", asyncio.Semaphore(5))
        response = await foreman.get_user_roles(user_id="mock1")
        assert response == {
            "unittest-role1": {
                "login": "unittest",
                "id": "mock1",
                "name": "unittest-role1",
            }
        }

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_user_roles_ids(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {"login": "unittest", "id": "mock1", "name": "unittest-role1"},
                {"id": "mock1", "name": "Default role"},
            ]
        }
        get_session.return_value.__aenter__.return_value = get_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.get_user_roles_ids(user_id="mock1")
        assert response == ["mock1"]
        get_session.return_value.__aexit__.return_value = {}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameter(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.put_parameter(host_name="host.example.com", name="host.example.com", value="host1")
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameters(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.put_parameters(host_name="host.example.com", params=[{"id": "host1"}])
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameters_by_name(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        params = [
            {"name": "host.example.com", "value": "host.example.com"},
            {"name": "host.example.com", "value": "host1"},
            {"name": "media", "value": "host1"},
        ]
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.put_parameters_by_name(host="hosts", params=params)
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameters_by_name_false(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        params = [{"name": "host.example.com", "value": "host1"}]
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.put_parameters_by_name(host="hosts", params=params)
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameter_by_name(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1", "identifier": "name"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response1 = await foreman.put_parameter_by_name(host="hosts", name="media", value="host.example.com")
        response2 = await foreman.put_parameter_by_name(host="hosts", name="host", value="host1.example.com")
        assert response1 and not response2

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_put_parameter_by_name_false(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        put_resp = AsyncMock()
        put_resp.status = 200
        put_session.return_value.__aenter__.return_value = put_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response1 = await foreman.put_parameter_by_name(host="hosts", name="media", value="host.example.com")
        response2 = await foreman.put_parameter_by_name(host="hosts", name="host", value="host.example.com")
        assert not response1 and not response2

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.put")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_verify_credentials(self, get_session, put_session):
        get_resp = AsyncMock()
        get_resp.status = 200
        get_session.return_value.__aenter__.return_value = get_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.verify_credentials()
        assert response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_verify_credentials_false(self, get_session):
        get_resp = AsyncMock()
        get_resp.status = 500
        get_session.return_value.__aenter__.return_value = get_resp
        foreman = Foreman(
            "https://example.com",
            "username",
            "password",
            asyncio.Semaphore(5),
        )
        response = await foreman.verify_credentials()
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_verify_credentials_raise_error(self, get_session):
        get_session.side_effect = Exception("Simulated error")
        foreman = Foreman("https://example.com", "username", "password")
        response = await foreman.verify_credentials()
        assert not response

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_idrac_host_without_mgmt(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1", "identifier": "name"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_idrac_host(host_name="host.example.com")
        assert not response1

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_idrac_host_with_mgmt(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "mgmt.example.com", "id": "host1", "identifier": "name"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_idrac_host(host_name="mgmt.example.com")
        assert response1 == "mgmt.example.com"

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_idrac_host_with_details_with_mgmt(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "mgmt.example.com", "id": "host1", "identifier": "name"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_idrac_host_with_details(host_name="mgmt.example.com")
        assert response1 == {
            "name": "mgmt.example.com",
            "id": "host1",
            "identifier": "name",
        }

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_idrac_host_with_details_without_mgmt(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{"name": "host.example.com", "id": "host1", "identifier": "name"}]}
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_idrac_host_with_details(host_name="host.example.com")
        assert not response1

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_available_os(self, get_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": [{
            "description": "",
            "major": "5",
            "minor": "3",
            "family": "Redhat",
            "release_name": "",
            "password_hash": "SHA256",
            "created_at": "2021-05-18 15:59:01 UTC",
            "updated_at": "2021-05-18 15:59:01 UTC",
            "id": 309172073,
            "name": "centos",
            "title": "centos 5.3"
        }]}
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_available_os()
        assert len(response1) == 1
