import pytest

from tests.config import (
    INTERFACE_1_REQUEST,
    INTERFACE_1_RESPONSE,
    INTERFACE_1_UPDATE_REQUEST,
    INTERFACE_1_UPDATE_RESPONSE,
)
from tests.helpers import unwrap_json

prefill_settings = ["clouds, hosts"]


class TestCreateInterfaces:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create an interface for an invalid host
        | THEN: Interface should not be created
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.post(
                f"/api/v3/interfaces/{host_name}",
                json=INTERFACE_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_arg(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create an interface with missing argument
        | THEN: Interface should not be created
        """
        auth_header = auth.get_auth_header()
        interface_request = INTERFACE_1_REQUEST[0].copy()
        del interface_request["name"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=interface_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: name"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_speed(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create an interface with invalid speed (< 0)
        | THEN: Interface should not be created
        """
        auth_header = auth.get_auth_header()
        interface_request = INTERFACE_1_REQUEST[0].copy()
        interface_request["speed"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=interface_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative: speed"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create an interface with valid data
        | THEN: Interface should be created
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=INTERFACE_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == INTERFACE_1_RESPONSE


class TestReadInterfaces:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to read interfaces for a valid host
        | THEN: Interface should be read
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/interfaces/{INTERFACE_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == INTERFACE_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to read interfaces for a valid host
        | THEN: Interface should be read
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{INTERFACE_1_REQUEST[1]}/interfaces",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [INTERFACE_1_RESPONSE]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to read interfaces for an invalid host
        | THEN: Interface should not be read
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{host_name}/interfaces",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_no_interfaces(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to read interfaces for a valid host with no interfaces
        | THEN: Interface should be read
        """
        auth_header = auth.get_auth_header()
        host_name = "host2.example.com"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{host_name}/interfaces",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == []

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_get_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateInterfaces
        | WHEN: User tries to read interfaces for all hosts
        | THEN: User should be able to read interfaces
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/interfaces",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [INTERFACE_1_RESPONSE]


class TestUpdateInterfaces:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to update an interface for an invalid host
        | THEN: Interface should not be updated
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/interfaces/{host_name}",
                json=INTERFACE_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to update an interface without specifying an ID for the interface.
        | THEN: Interface should not be updated
        """
        auth_header = auth.get_auth_header()
        update_request = INTERFACE_1_UPDATE_REQUEST.copy()
        del update_request["id"]
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: id"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_wrong_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to update an interface with an ID that doesn't match any interface.
        | THEN: Interface should not be updated
        """
        auth_header = auth.get_auth_header()
        update_request = INTERFACE_1_UPDATE_REQUEST.copy()
        update_request["id"] = 42
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Interface not found: {update_request['id']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to update an interface with valid data
        | THEN: Interface should be updated
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=INTERFACE_1_UPDATE_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == INTERFACE_1_UPDATE_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_speed(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to update an interface with invalid speed
        | THEN: Interface should not be updated
        """
        auth_header = auth.get_auth_header()
        update_request = INTERFACE_1_UPDATE_REQUEST.copy()
        update_request["speed"] = -1
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}",
                json=update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative: speed"


class TestDeleteInterfaces:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to delete an interface for an invalid host
        | THEN: Interface should not be deleted
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/interfaces/{host_name}/{INTERFACE_1_REQUEST[0]['name']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_wrong_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to delete an interface with an ID that doesn't match any interface.
        | THEN: Interface should not be deleted
        """
        auth_header = auth.get_auth_header()
        invalid_id = 42
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}/{invalid_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Interface not found: {invalid_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to delete an interface with valid data
        | THEN: Interface should be deleted
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/interfaces/{INTERFACE_1_REQUEST[1]}/{INTERFACE_1_RESPONSE['name']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Interface deleted"
