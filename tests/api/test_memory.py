import pytest

from tests.config import MEMORY_1_REQUEST, MEMORY_1_RESPONSE, MEMORY_3_REQUEST, MEMORY_3_RESPONSE
from tests.helpers import unwrap_json

prefill_settings = ["clouds, hosts"]


class TestCreateMemory:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory for non-existing host
        | THEN: User should not be able to create memory
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{host_name}",
                json=MEMORY_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_handle(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory with without passing the handle argument
        | THEN: User should not be able to create memory
        """
        auth_header = auth.get_auth_header()
        memory_request = MEMORY_1_REQUEST[0].copy()
        del memory_request["handle"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_1_REQUEST[1]}",
                json=memory_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: handle"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_size(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory with without passing the size argument
        | THEN: User should not be able to create memory
        """
        auth_header = auth.get_auth_header()
        memory_request = MEMORY_1_REQUEST[0].copy()
        del memory_request["size_gb"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_1_REQUEST[1]}",
                json=memory_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: size_gb"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_size(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory with invalid size argument (<= 0)
        | THEN: User should not be able to create memory
        """
        auth_header = auth.get_auth_header()
        memory_request = MEMORY_1_REQUEST[0].copy()
        memory_request["size_gb"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_1_REQUEST[1]}",
                json=memory_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: size_gb"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory for existing host (creates two, for testing get all in TestReadMemory)
        | THEN: User should be able to create memory
        """
        auth_header = auth.get_auth_header()
        response_1 = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_1_REQUEST[1]}",
                json=MEMORY_1_REQUEST[0],
                headers=auth_header,
            )
        )
        response_2 = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_3_REQUEST[1]}",
                json=MEMORY_3_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response_1.status_code == 200
        assert response_1.json == MEMORY_1_RESPONSE
        assert response_2.status_code == 200
        assert response_2.json == MEMORY_3_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_duplicate_handle(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create memory for existing host with duplicate handle
        | THEN: User should not be able to create memory
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/memory/{MEMORY_1_REQUEST[1]}",
                json=MEMORY_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert (
            response.json["message"] == f"Memory with this handle ({MEMORY_1_REQUEST[0]['handle']}) already "
            "exists for this host."
        )


class TestReadMemory:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to read memory for existing host that has memory
        | THEN: User should be able to read memory
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/memory/{MEMORY_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == MEMORY_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to read memory for existing host that has memory
        | THEN: User should be able to read memory
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{MEMORY_1_REQUEST[1]}/memory",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [MEMORY_1_RESPONSE]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to read memory for an invalid host
        | THEN: User should be able to see an error message
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{host_name}/memory",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_get_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to read memory for all hosts
        | THEN: User should be able to read memory
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/memory",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [MEMORY_1_RESPONSE, MEMORY_3_RESPONSE]


class TestDeleteMemory:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_memory_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to delete non-existing memory for existing host
        | THEN: User should not be able to delete memory
        """
        auth_header = auth.get_auth_header()
        invalid_memory_id = 42
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/memory/{invalid_memory_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Memory not found: {invalid_memory_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds, hosts and memory from TestCreateMemory
        | WHEN: User tries to delete memory for existing host that has memory and specifies correct memory id
        | THEN: User should be able to delete memory
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/memory/{MEMORY_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Memory deleted"
