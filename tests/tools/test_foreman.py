#!/usr/bin/env python3
import asyncio
import logging
from unittest.mock import AsyncMock, patch

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
        get_resp.json.return_value = {
            "results": [
                {
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
                    "title": "centos 5.3",
                }
            ]
        }
        get_session.return_value.__aenter__.return_value = get_resp

        foreman = Foreman("https://example.com", "username", "password")
        response1 = await foreman.get_available_os()
        assert len(response1) == 1


class TestPrepareHostProvisioning(object):
    def _make_foreman(self):
        return Foreman(
            "https://example.com",
            "username",
            "password",
            semaphore=asyncio.Semaphore(5),
        )

    @pytest.mark.asyncio
    async def test_success_single_ptable(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(return_value=1)
        foreman.get_mediums = AsyncMock(return_value=[{"id": 10, "name": "RHEL Local"}])
        foreman.get_ptables = AsyncMock(return_value=[{"id": 20, "name": "generic-rhel"}])
        foreman.mark_for_build = AsyncMock(return_value=True)
        foreman.put_parameters = AsyncMock(return_value=True)
        foreman.get_user_id = AsyncMock(return_value=100)
        foreman.get_host_id = AsyncMock(return_value=200)
        foreman.put_element = AsyncMock(return_value=True)

        with caplog.at_level(logging.INFO):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "RHEL 9.2")

        assert result is True
        assert "Selected ptable 'generic-rhel'" in caplog.text
        assert "Selected medium 'RHEL Local'" in caplog.text
        foreman.put_parameters.assert_called_once()
        data = foreman.put_parameters.call_args[0][1]
        assert data["ptable_id"] == 20
        assert data["medium_id"] == 10
        assert data["operatingsystem_id"] == 1
        foreman.mark_for_build.assert_called_once_with("host01.example.com")
        foreman.get_user_id.assert_called_once_with("cloud01")
        foreman.get_host_id.assert_called_once_with("host01.example.com")
        foreman.put_element.assert_called_once_with("hosts", 200, "owner_id", 100)

    @pytest.mark.asyncio
    async def test_os_not_found(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(return_value=None)

        with caplog.at_level(logging.ERROR):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "NonExistent OS")

        assert result is False
        assert "OS type NonExistent OS not found" in caplog.text

    @pytest.mark.asyncio
    async def test_no_ptables(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(return_value=1)
        foreman.get_mediums = AsyncMock(return_value=[{"id": 10, "name": "RHEL Local"}])
        foreman.get_ptables = AsyncMock(return_value=[])

        with caplog.at_level(logging.ERROR):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "RHEL 9.2")

        assert result is False
        assert "No ptable found" in caplog.text

    @pytest.mark.asyncio
    async def test_no_mediums(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(return_value=1)
        foreman.get_mediums = AsyncMock(return_value=[])

        with caplog.at_level(logging.ERROR):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "RHEL 9.2")

        assert result is False
        assert "No medium found" in caplog.text

    @pytest.mark.asyncio
    async def test_multiple_ptables_warning(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(return_value=1)
        foreman.get_mediums = AsyncMock(return_value=[{"id": 10, "name": "RHEL Local"}])
        foreman.get_ptables = AsyncMock(
            return_value=[
                {"id": 20, "name": "generic-bios"},
                {"id": 21, "name": "generic-uefi"},
            ]
        )
        foreman.mark_for_build = AsyncMock(return_value=True)
        foreman.put_parameters = AsyncMock(return_value=True)
        foreman.get_user_id = AsyncMock(return_value=100)
        foreman.get_host_id = AsyncMock(return_value=200)
        foreman.put_element = AsyncMock(return_value=True)

        with caplog.at_level(logging.WARNING):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "RHEL 9.2")

        assert result is True
        assert "has 2 ptable" in caplog.text
        assert "defaulting to first: 'generic-bios'" in caplog.text
        data = foreman.put_parameters.call_args[0][1]
        assert data["ptable_id"] == 20

    @pytest.mark.asyncio
    async def test_exception_uses_module_logger(self, caplog):
        foreman = self._make_foreman()
        foreman.get_os_id = AsyncMock(side_effect=Exception("connection failed"))

        with caplog.at_level(logging.ERROR):
            result = await foreman.prepare_host_provisioning("host01.example.com", "cloud01", "RHEL 9.2")

        assert result is False
        assert "Error setting up Foreman for host01.example.com" in caplog.text
        assert "connection failed" in caplog.text


class TestForemanRbac(object):
    """Tests for the RBAC helper methods added to support foreman_setup.py."""

    # ------------------------------------------------------------------
    # delete()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_delete_returns_true_on_200(self, delete_session):
        resp = AsyncMock()
        resp.status = 200
        delete_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert await foreman.delete("/filters/1")

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_delete_returns_true_on_204(self, delete_session):
        resp = AsyncMock()
        resp.status = 204
        delete_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert await foreman.delete("/filters/1")

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_delete_returns_false_on_error_status(self, delete_session):
        resp = AsyncMock()
        resp.status = 404
        delete_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert not await foreman.delete("/filters/99")

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @pytest.mark.asyncio
    async def test_delete_returns_false_on_exception(self, delete_session):
        delete_session.side_effect = Exception("network error")
        foreman = Foreman("https://example.com", "username", "password")
        assert not await foreman.delete("/filters/1")

    # ------------------------------------------------------------------
    # post()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_returns_result_and_status(self, post_session):
        resp = AsyncMock()
        resp.status = 201
        resp.json.return_value = {"id": 42, "name": "testrole"}
        post_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        result, status = await foreman.post("/roles", {"role": {"name": "testrole"}})
        assert status == 201
        assert result == {"id": 42, "name": "testrole"}

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_returns_empty_on_exception(self, post_session):
        post_session.side_effect = Exception("connection refused")
        foreman = Foreman("https://example.com", "username", "password")
        result, status = await foreman.post("/roles", {})
        assert result == {}
        assert status == 0

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @pytest.mark.asyncio
    async def test_post_redacts_password_in_debug_log(self, post_session, caplog):
        resp = AsyncMock()
        resp.status = 201
        resp.json.return_value = {"id": 1}
        post_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        with caplog.at_level(logging.DEBUG, logger="quads.tools.external.foreman"):
            await foreman.post("/users", {"user": {"login": "cloud01", "password": "supersecret"}})
        assert "supersecret" not in caplog.text
        assert "POST: /users" in caplog.text

    # ------------------------------------------------------------------
    # get_permission_ids()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_permission_ids(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "view_hosts", "id": 10}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        ids = await foreman.get_permission_ids(["view_hosts"])
        assert ids == [10]

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_permission_ids_not_found(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "other_perm", "id": 99}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        ids = await foreman.get_permission_ids(["view_hosts"])
        assert ids == []

    # ------------------------------------------------------------------
    # get_or_create_role()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_role_existing(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "clouduser_hosts", "id": 5}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        role_id = await foreman.get_or_create_role("clouduser_hosts")
        assert role_id == 5

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_role_creates_new(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 201
        post_resp.json.return_value = {"id": 7, "name": "clouduser_hosts"}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        role_id = await foreman.get_or_create_role("clouduser_hosts")
        assert role_id == 7

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_role_returns_none_on_failure(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 500
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        role_id = await foreman.get_or_create_role("clouduser_hosts")
        assert role_id is None

    # ------------------------------------------------------------------
    # get_filters_for_role()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_filters_for_role(self, get_session):
        filters = [{"id": 1, "permissions": [{"name": "view_hosts"}]}]
        resp = AsyncMock()
        resp.json.return_value = {"results": filters}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        result = await foreman.get_filters_for_role(role_id=5)
        assert result == filters

    # ------------------------------------------------------------------
    # role_has_permission()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_role_has_permission_found(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"id": 1, "permissions": [{"name": "view_hosts"}]}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert await foreman.role_has_permission(role_id=5, permission_name="view_hosts")

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_role_has_permission_not_found(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"id": 1, "permissions": [{"name": "edit_hosts"}]}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert not await foreman.role_has_permission(role_id=5, permission_name="view_hosts")

    # ------------------------------------------------------------------
    # cleanup_duplicate_filters()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_cleanup_duplicate_filters_no_duplicates(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {
            "results": [
                {"id": 1, "permissions": [{"name": "view_hosts"}]},
                {"id": 2, "permissions": [{"name": "edit_hosts"}]},
            ]
        }
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        removed = await foreman.cleanup_duplicate_filters(role_id=5)
        assert removed == 0

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_cleanup_duplicate_filters_removes_duplicates(self, get_session, delete_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {
            "results": [
                {"id": 1, "permissions": [{"name": "view_hosts"}]},
                {"id": 2, "permissions": [{"name": "view_hosts"}]},
            ]
        }
        get_session.return_value.__aenter__.return_value = get_resp

        del_resp = AsyncMock()
        del_resp.status = 200
        delete_session.return_value.__aenter__.return_value = del_resp

        foreman = Foreman("https://example.com", "username", "password")
        removed = await foreman.cleanup_duplicate_filters(role_id=5)
        assert removed == 1

    # ------------------------------------------------------------------
    # ensure_filter()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_ensure_filter_already_exists(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"id": 1, "permissions": [{"name": "view_hosts"}]}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        result = await foreman.ensure_filter(5, ["view_hosts"])
        assert result is True

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_ensure_filter_creates_new(self, get_session, post_session):
        # No permission → no filter → GET permission id → POST filter
        get_resp = AsyncMock()
        get_resp.json.side_effect = [
            {"results": []},  # get_filters_for_role (role_has_permission check)
            {"results": [{"name": "view_hosts", "id": 10}]},  # get_permission_ids
        ]
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 201
        post_resp.json.return_value = {"id": 99}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        result = await foreman.ensure_filter(5, ["view_hosts"], search="user.login = current_user")
        assert result is True

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_ensure_filter_fails(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.side_effect = [
            {"results": []},
            {"results": [{"name": "view_hosts", "id": 10}]},
        ]
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 500
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        result = await foreman.ensure_filter(5, ["view_hosts"])
        assert result is False

    # ------------------------------------------------------------------
    # get_usergroup_id()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_usergroup_id_found(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "cloudusers", "id": 3}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        group_id = await foreman.get_usergroup_id("cloudusers")
        assert group_id == 3

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_usergroup_id_not_found(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        group_id = await foreman.get_usergroup_id("cloudusers")
        assert group_id is None

    # ------------------------------------------------------------------
    # get_or_create_usergroup()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_usergroup_existing(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"name": "cloudusers", "id": 3}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        group_id = await foreman.get_or_create_usergroup("cloudusers", [1, 2])
        assert group_id == 3

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_usergroup_creates_new(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 201
        post_resp.json.return_value = {"id": 8}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        group_id = await foreman.get_or_create_usergroup("cloudusers", [1, 2])
        assert group_id == 8

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_usergroup_returns_none_on_failure(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 500
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        group_id = await foreman.get_or_create_usergroup("cloudusers", [1, 2])
        assert group_id is None

    # ------------------------------------------------------------------
    # add_user_to_usergroup()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_add_user_to_usergroup_already_member(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"users": [{"id": 20}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        assert await foreman.add_user_to_usergroup(group_id=3, user_id=20)

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_add_user_to_usergroup_new_member(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"users": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 201
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        assert await foreman.add_user_to_usergroup(group_id=3, user_id=20)

    # ------------------------------------------------------------------
    # cleanup_duplicate_memberships()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_cleanup_duplicate_memberships_no_duplicates(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"users": [{"id": 10}, {"id": 20}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        removed = await foreman.cleanup_duplicate_memberships(group_id=3)
        assert removed == 0

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.delete")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_cleanup_duplicate_memberships_removes_duplicates(self, get_session, delete_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"users": [{"id": 10}, {"id": 10}]}
        get_session.return_value.__aenter__.return_value = get_resp

        del_resp = AsyncMock()
        del_resp.status = 200
        delete_session.return_value.__aenter__.return_value = del_resp

        foreman = Foreman("https://example.com", "username", "password")
        removed = await foreman.cleanup_duplicate_memberships(group_id=3)
        assert removed == 1

    # ------------------------------------------------------------------
    # get_or_create_cloud_user()
    # ------------------------------------------------------------------

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_cloud_user_existing(self, get_session):
        resp = AsyncMock()
        resp.json.return_value = {"results": [{"login": "cloud01", "id": 55}]}
        get_session.return_value.__aenter__.return_value = resp
        foreman = Foreman("https://example.com", "username", "password")
        user_id = await foreman.get_or_create_cloud_user("cloud01", "pw", "q@example.com")
        assert user_id == 55

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_cloud_user_creates_new(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 201
        post_resp.json.return_value = {"id": 66}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        user_id = await foreman.get_or_create_cloud_user("cloud01", "pw", "q@example.com")
        assert user_id == 66

    @patch("quads.tools.external.foreman.aiohttp.ClientSession.post")
    @patch("quads.tools.external.foreman.aiohttp.ClientSession.get")
    @pytest.mark.asyncio
    async def test_get_or_create_cloud_user_returns_none_on_failure(self, get_session, post_session):
        get_resp = AsyncMock()
        get_resp.json.return_value = {"results": []}
        get_session.return_value.__aenter__.return_value = get_resp

        post_resp = AsyncMock()
        post_resp.status = 500
        post_resp.json.return_value = {}
        post_session.return_value.__aenter__.return_value = post_resp

        foreman = Foreman("https://example.com", "username", "password")
        user_id = await foreman.get_or_create_cloud_user("cloud01", "pw", "q@example.com")
        assert user_id is None
