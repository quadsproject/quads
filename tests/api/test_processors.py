import pytest

from tests.config import (
    PROCESSOR_1_REQUEST,
    PROCESSOR_1_RESPONSE,
    PROCESSOR_2_REQUEST,
    PROCESSOR_2_RESPONSE,
    PROCESSOR_3_REQUEST,
    PROCESSOR_4_REQUEST,
)
from tests.helpers import unwrap_json

prefill_settings = ["clouds, hosts"]


class TestCreateProcessors:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a processor for non-existing host
        | THEN: User should not be able to create a processor
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{host_name}",
                json=PROCESSOR_1_REQUEST[0],
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
        | WHEN: User tries to create a processor for valid host without passing one of the required arguments (vendor)
        | THEN: User should not be able to create a processor
        """
        auth_header = auth.get_auth_header()
        processor_request = PROCESSOR_1_REQUEST[0].copy()
        del processor_request["vendor"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_1_REQUEST[1]}",
                json=processor_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: vendor"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_core_count(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a processor for valid host with invalid core count argument (<= 0)
        | THEN: User should not be able to create a processor
        """
        auth_header = auth.get_auth_header()
        processor_request = PROCESSOR_4_REQUEST[0].copy()
        processor_request["cores"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_4_REQUEST[1]}",
                json=processor_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: cores"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_thread_count(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a processor for valid host with invalid thread count argument (<= 0)
        | THEN: User should not be able to create a processor
        """
        auth_header = auth.get_auth_header()
        processor_request = PROCESSOR_4_REQUEST[0].copy()
        processor_request["threads"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_4_REQUEST[1]}",
                json=processor_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: threads"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a processor for valid host with valid arguments
        | THEN: User should be able to create a processor
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_1_REQUEST[1]}",
                json=PROCESSOR_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == PROCESSOR_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_another(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create/add another processors to valid host that has a processor already
        | THEN: User should be able to create/add another processors
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_2_REQUEST[1]}",
                json=PROCESSOR_2_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == PROCESSOR_2_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_duplicate_handle(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create processor for existing host with duplicate handle
        | THEN: User should not be able to create the processor
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/processors/{PROCESSOR_1_REQUEST[1]}",
                json=PROCESSOR_1_REQUEST[0],
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert (
            response.json["message"] == f"Processor with this handle ({PROCESSOR_1_REQUEST[0]['handle']}) already "
            "exists for this host."
        )


class TestReadProcessors:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and processors from TestCreateProcessors
        | WHEN: User tries to get processors for non-existing host
        | THEN: User should not be able to get processors
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{host_name}/processors",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and processors from TestCreateProcessors
        | WHEN: User tries to get processors for valid host
        | THEN: User should be able to get processors
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{PROCESSOR_1_REQUEST[1]}/processors",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [PROCESSOR_1_RESPONSE, PROCESSOR_2_RESPONSE]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_no_processors(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and processors from TestCreateProcessors
        | WHEN: User tries to get processors for valid host that has no processors
        | THEN: User should be able to get processors
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{PROCESSOR_3_REQUEST[1]}/processors",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == []


class TestDeleteProcessors:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_processor_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and processors from TestCreateProcessors
        | WHEN: User tries to delete non-existing processor (specified by ID) for valid host
        | THEN: User should not be able to delete processor
        """
        auth_header = auth.get_auth_header()
        invalid_processor_id = 42
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/processors/{invalid_processor_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Processor not found: {invalid_processor_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and processors from TestCreateProcessors
        | WHEN: User tries to delete processor for valid host (specified by a valid ID)
        | THEN: User should be able to delete processor
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/processors/{PROCESSOR_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Processor deleted"
