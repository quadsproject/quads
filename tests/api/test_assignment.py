from datetime import datetime
from unittest.mock import patch

import pytest

from tests.config import (
    ASSIGNMENT_1_REQUEST,
    ASSIGNMENT_1_RESPONSE,
    ASSIGNMENT_1_UPDATE_REQUEST,
    ASSIGNMENT_1_UPDATE_RESPONSE,
    ASSIGNMENT_2_REQUEST,
    ASSIGNMENT_2_RESPONSE,
)
from tests.helpers import unwrap_json

prefill_settings = ["clouds, vlans"]
prefill_schedule = ["clouds, vlans, hosts, assignments, schedules"]


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
        | WHEN: User tries to delete an assignment without specifying an ID in the path
        | THEN: User should get a 405 Method Not Allowed
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/assignments/",
                headers=auth_header,
            )
        )
        assert response.status_code == 405

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
                f"/api/v3/assignments/{invalid_assignment_id}/",
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
                f"/api/v3/assignments/{ASSIGNMENT_1_RESPONSE['id']}/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Assignment deleted"


class TestCreateSelfAssignment:
    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_owner_derived_from_current_user(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans with self-scheduling enabled
        | WHEN: User creates a self-assignment with a different owner in request body
        | THEN: Owner should be derived from current user, not from request body
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 1,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("grafuls@redhat.com")
        assignment_request = {
            "description": "Test self assignment",
            "owner": "attacker",
            "cloud": "cloud05",
            "ticket": "SELF-001",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["owner"] == "grafuls"

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_owner_not_from_request_body(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans with self-scheduling enabled
        | WHEN: User omits owner from request body
        | THEN: Owner should be derived from current user
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 1,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("grafuls@redhat.com")
        assignment_request = {
            "description": "Test self assignment no owner",
            "cloud": "cloud04",
            "ticket": "SELF-002",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json=assignment_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["owner"] == "grafuls"


class TestExpirations:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_expirations(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User tries to read expiring schedules
        | THEN: User should be able to read the currently active schedules with expiration data
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/assignments/expirations/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert isinstance(response.json, list)

    @patch("quads.server.dao.schedule.ScheduleDao.get_expiring_schedules")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_expirations_empty(self, mock_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds and vlans but no schedules
        | WHEN: User tries to read expiring schedules
        | THEN: User should get an empty list
        """
        mock_get.return_value = []
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/assignments/expirations/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == []
