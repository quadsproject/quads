import pytest

from tests.config import (
    DISK_1_REQUEST,
    DISK_1_RESPONSE,
    DISK_1_UPDATE_REQUEST,
    DISK_1_UPDATE_RESPONSE,
    DISK_2_REQUEST,
    DISK_2_RESPONSE,
    DISK_3_REQUEST,
)
from tests.helpers import unwrap_json

prefill_settings = ["clouds, hosts"]


class TestCreateDisks:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with valid data, for an invalid host
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{host_name}",
                json=dict(DISK_1_REQUEST[0]),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_disk_type(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with missing disk_type argument
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        disk_request = DISK_1_REQUEST[0].copy()
        del disk_request["disk_type"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(disk_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: disk_type"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_size(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with missing size_gb argument
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        disk_request = DISK_1_REQUEST[0].copy()
        del disk_request["size_gb"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(disk_request),
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
        | WHEN: User tries to create a disk with invalid size_gb argument (<= 0)
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        disk_request = DISK_1_REQUEST[0].copy()
        disk_request["size_gb"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(disk_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: size_gb"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_count(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with missing count argument
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        disk_request = DISK_1_REQUEST[0].copy()
        del disk_request["count"]
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(disk_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: count"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_count(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with invalid count (<= 0)
        | THEN: Disk should not be created
        """
        auth_header = auth.get_auth_header()
        disk_request = DISK_1_REQUEST[0].copy()
        disk_request["count"] = -1
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(disk_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: count"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disk with valid data, for a valid host
        | THEN: Disk should be created
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_1_REQUEST[1]}",
                json=dict(DISK_1_REQUEST[0]),
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == DISK_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_multiple_per_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to create a disks with valid data, for a valid host that already has disk/s
        | THEN: Disks should be created
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                f"/api/v3/disks/{DISK_2_REQUEST[1]}",
                json=dict(DISK_2_REQUEST[0]),
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == DISK_2_RESPONSE


class TestReadDisks:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to read disks for an invalid host
        | THEN: Disks should not be read
        """
        auth_header = auth.get_auth_header()
        invalid_id = 42
        response = unwrap_json(
            test_client.get(
                f"/api/v3/disks/{invalid_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Disk not found: {invalid_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to read disks for a valid host
        | THEN: Disks should be read
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/disks/{DISK_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == DISK_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_empty(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts
        | WHEN: User tries to read disks for a valid host that has no disks
        | THEN: Disks should be read
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts/{DISK_3_REQUEST[1]}/disks",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == []


class TestUpdateDisks:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to update disks for an invalid host
        | THEN: Disks should not be updated
        """
        auth_header = auth.get_auth_header()
        host_name = "invalid_host"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/disks/{host_name}",
                json=dict(DISK_1_REQUEST[0]),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {host_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_disk_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to update disks for a valid host, but an invalid disk ID
        | THEN: Disks should not be updated
        """
        auth_header = auth.get_auth_header()
        invalid_id = 42
        update_request = DISK_1_UPDATE_REQUEST[0].copy()
        update_request["disk_id"] = invalid_id
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/disks/{DISK_1_UPDATE_REQUEST[1]}",
                json=dict(update_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Disk not found for {DISK_1_UPDATE_REQUEST[1]}: {invalid_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to update disks for a valid host with a valid request
        | THEN: Disks should be updated
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/disks/{DISK_1_UPDATE_REQUEST[1]}",
                json=dict(DISK_1_UPDATE_REQUEST[0]),
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == DISK_1_UPDATE_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_negative_count(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to update disks for a valid host, but an invalid value for the count field
        | THEN: Disks should not be updated
        """
        auth_header = auth.get_auth_header()
        invalid_count = -1
        update_request = DISK_1_UPDATE_REQUEST[0].copy()
        update_request["count"] = invalid_count
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/disks/{DISK_1_UPDATE_REQUEST[1]}",
                json=dict(update_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: count"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_negative_size(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to update disks for a valid host, but an invalid value for the size_gb field
        | THEN: Disks should not be updated
        """
        auth_header = auth.get_auth_header()
        invalid_size = -1
        update_request = DISK_1_UPDATE_REQUEST[0].copy()
        update_request["size_gb"] = invalid_size
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/disks/{DISK_1_UPDATE_REQUEST[1]}",
                json=dict(update_request),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Argument can't be negative or zero: size_gb"


class TestDeleteDisks:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to delete a disk with valid ID for a valid host
        | THEN: Disks should be deleted
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/disks/{DISK_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Disk deleted"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token, clouds and hosts and disks from TestCreateDisks
        | WHEN: User tries to delete a disk with invalid ID for a valid host
        | THEN: Disks should not be deleted
        """
        auth_header = auth.get_auth_header()
        invalid_id = 42
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/disks/{invalid_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Disk not found: {invalid_id}"
