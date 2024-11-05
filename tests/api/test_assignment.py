import pytest

from datetime import datetime

from tests.helpers import unwrap_json
from tests.config import (
    ASSIGNMENT_1_REQUEST,
    ASSIGNMENT_1_RESPONSE,
    ASSIGNMENT_1_UPDATE_REQUEST,
    ASSIGNMENT_1_UPDATE_RESPONSE,
    ASSIGNMENT_2_REQUEST,
    ASSIGNMENT_2_RESPONSE,
)

prefill_settings = ["clouds, vlans"]


class TestCreateAssignments:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_required(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment without passing one of the required arguments
        | THEN: User should not be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        assignment_request = ASSIGNMENT_1_REQUEST.copy()
        del assignment_request["owner"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: owner"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment without specifying a cloud
        | THEN: User should be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        assignment_request = ASSIGNMENT_1_REQUEST.copy()
        del assignment_request["cloud"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment for a non-existent cloud
        | THEN: User should not be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        assignment_request = ASSIGNMENT_1_REQUEST.copy()
        assignment_request["cloud"] = "invalid_cloud"
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {assignment_request['cloud']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_vlan_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment for a non-existent vlan
        | THEN: User should not be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        assignment_request = ASSIGNMENT_1_REQUEST.copy()
        assignment_request["vlan"] = 42
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Vlan not found: {assignment_request['vlan']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment
        | THEN: User should be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        assignment_requests = [ASSIGNMENT_1_REQUEST, ASSIGNMENT_2_REQUEST]
        assignment_responses = [ASSIGNMENT_1_RESPONSE, ASSIGNMENT_2_RESPONSE]
        for response, request in zip(assignment_responses, assignment_requests):
            assignment_response = response.copy()
            response = unwrap_json(
                test_client.post(
                    "/api/v3/assignments",
                    json=request,
                    headers=auth_header,
                )
            )
            assignment_response["created_at"] = response.json["created_at"]
            assignment_response["cloud"]["last_redefined"] = response.json["cloud"]["last_redefined"]
            duration = datetime.utcnow() - datetime.strptime(response.json["created_at"], "%a, %d %b %Y %H:%M:%S GMT")
            assert duration.total_seconds() < 5
            assert response.status_code == 200
            assert response.json == assignment_response

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_already_assigned_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans
        | WHEN: User tries to create an assignment for a cloud that already has an assignment
        | THEN: User should not be able to create an assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json=ASSIGNMENT_1_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"There is an already active assignment for {ASSIGNMENT_1_REQUEST['cloud']}"


class TestReadAssignment:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_assignment_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read an assignment by its ID that does not exist
        | THEN: User should not be able to read an assignment
        """
        auth_header = auth.get_auth_header()
        invalid_assignment_id = 42
        response = unwrap_json(
            test_client.get(
                f"/api/v3/assignments/{invalid_assignment_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Assignment not found: {invalid_assignment_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read an assignment by its ID that exists
        | THEN: User should be able to read an assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/assignments/{ASSIGNMENT_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assignment_response = ASSIGNMENT_1_RESPONSE.copy()
        assignment_response["cloud"]["last_redefined"] = response.json["cloud"]["last_redefined"]
        assignment_response["created_at"] = response.json["created_at"]
        assert response.status_code == 200
        assert response.json == assignment_response

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read all assignments
        | THEN: User should be able to read all assignments
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/assignments",
                headers=auth_header,
            )
        )
        assignment_responses = [
            ASSIGNMENT_1_RESPONSE.copy(),
            ASSIGNMENT_2_RESPONSE.copy(),
        ]
        for resp, assignment_response in zip(response.json, assignment_responses):
            assignment_response["cloud"]["last_redefined"] = resp["cloud"]["last_redefined"]
            assignment_response["created_at"] = resp["created_at"]
        assert response.status_code == 200
        assert response.json == assignment_responses

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read an assignment for a cloud, valid cloud name specified
        | THEN: User should be able to read an assignment for the cloud
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/assignments/active/{ASSIGNMENT_1_REQUEST['cloud']}",
                headers=auth_header,
            )
        )
        assignment_response = ASSIGNMENT_1_RESPONSE.copy()
        assignment_response["cloud"]["last_redefined"] = response.json["cloud"]["last_redefined"]
        assignment_response["created_at"] = response.json["created_at"]
        assert response.status_code == 200
        assert response.json == assignment_response

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_name(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read an assignment for a cloud, invalid cloud name specified
        | THEN: User should not be able to read an assignment for the cloud
        """
        auth_header = auth.get_auth_header()
        invalid_cloud_name = "invalid_cloud_name"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/assignments/active/{invalid_cloud_name}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {invalid_cloud_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_active_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read all active assignments
        | THEN: User should be able to read all active assignments
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/assignments/active",
                headers=auth_header,
            )
        )
        assignment_responses = [
            ASSIGNMENT_1_RESPONSE.copy(),
            ASSIGNMENT_2_RESPONSE.copy(),
        ]
        for resp, assignment_response in zip(response.json, assignment_responses):
            assignment_response["cloud"]["last_redefined"] = resp["cloud"]["last_redefined"]
            assignment_response["created_at"] = resp["created_at"]
        assert response.status_code == 200
        assert response.json == assignment_responses

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_field_filter(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to read active assignments which respond to an invalid filter
        | THEN: User should not be able to read any assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/assignments/?SomeField=value",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "SomeField is not a valid field."


class TestUpdateAssignment:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_assignment_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to update an assignment by its ID that does not exist
        | THEN: User should not be able to update an assignment
        """
        auth_header = auth.get_auth_header()
        invalid_assignment_id = 42
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/assignments/{invalid_assignment_id}",
                json=ASSIGNMENT_1_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Assignment not found: {invalid_assignment_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to update an assignment by its ID, invalid cloud name specified
        | THEN: User should not be able to update an assignment
        """
        auth_header = auth.get_auth_header()
        invalid_cloud_name = "invalid_cloud_name"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/assignments/{ASSIGNMENT_1_RESPONSE['id']}",
                json={"cloud": invalid_cloud_name},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {invalid_cloud_name}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_vlan_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to update an assignment by its ID, invalid vlan name specified
        | THEN: User should not be able to update an assignment
        """
        auth_header = auth.get_auth_header()
        invalid_vlan_id = 42
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/assignments/{ASSIGNMENT_1_RESPONSE['id']}",
                json={"vlan": invalid_vlan_id},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert (
            response.json["message"]
            == f"Vlan not found: {invalid_vlan_id}, for clearing use any of: ['none', '0', 'no', 'nada', 'clear']"
        )

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to update an assignment by its ID
        | THEN: User should be able to update an assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/assignments/{ASSIGNMENT_1_RESPONSE['id']}",
                json=ASSIGNMENT_1_UPDATE_REQUEST,
                headers=auth_header,
            )
        )
        assignment_response = ASSIGNMENT_1_UPDATE_RESPONSE.copy()
        assignment_response["cloud"]["last_redefined"] = response.json["cloud"]["last_redefined"]
        assignment_response["created_at"] = response.json["created_at"]
        assert response.status_code == 200
        assert response.json == assignment_response


class TestDeleteAssignment:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_id(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to delete an assignment by its ID, that is not specified
        | THEN: User should not be able to delete an assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/assignments",
                json={},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: id"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_assignment_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to delete an assignment by its ID that does not exist
        | THEN: User should not be able to delete an assignment
        """
        auth_header = auth.get_auth_header()
        invalid_assignment_id = 42
        response = unwrap_json(
            test_client.delete(
                "/api/v3/assignments",
                json={"id": invalid_assignment_id},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Assignment not found: {invalid_assignment_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans with assignments from TestCreateAssignment
        | WHEN: User tries to delete an assignment by its ID
        | THEN: User should be able to delete an assignment
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/assignments",
                json={"id": ASSIGNMENT_1_RESPONSE["id"]},
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Assignment deleted"
