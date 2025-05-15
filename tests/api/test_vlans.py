from tests.config import (
    VLAN_1_REQUEST,
    VLAN_1_RESPONSE,
    VLAN_1_UPDATE_REQUEST,
    VLAN_1_UPDATE_RESPONSE,
    VLAN_2_REQUEST,
    VLAN_2_RESPONSE,
)
from tests.helpers import unwrap_json


class TestCreateVLANs:
    def test_invalid_missing_arg(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to create a VLAN without a required argument
        | THEN: User should not be able to create a VLAN
        """
        auth_header = auth.get_auth_header()
        vlan_request = VLAN_1_REQUEST.copy()
        del vlan_request["ip_range"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/vlans",
                headers=auth_header,
                json=vlan_request,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: ip_range"

    def test_valid(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to create a VLAN with valid arguments
        | THEN: User should be able to create a VLAN
        """
        auth_header = auth.get_auth_header()
        response_1 = unwrap_json(
            test_client.post(
                "/api/v3/vlans",
                headers=auth_header,
                json=VLAN_1_REQUEST,
            )
        )
        assert response_1.status_code == 200
        assert response_1.json == VLAN_1_RESPONSE
        response_2 = unwrap_json(
            test_client.post(
                "/api/v3/vlans",
                headers=auth_header,
                json=VLAN_2_REQUEST,
            )
        )
        assert response_2.status_code == 200
        assert response_2.json == VLAN_2_RESPONSE

    def test_invalid_already_exists(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLAN with `vlan_id` == 1 already created
        | WHEN: User tries to create a VLAN with a `vlan_id` that already exists
        | THEN: User should not be able to create a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/vlans",
                headers=auth_header,
                json=VLAN_1_REQUEST,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Vlan {VLAN_1_REQUEST['vlan_id']} already exists"


class TestReadVLANs:
    def test_invalid_vlan_not_found(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to read a VLAN that does not exist
        | THEN: User should not be able to read a VLAN
        """
        auth_header = auth.get_auth_header()
        invalid_vlan_id = 42
        response = unwrap_json(
            test_client.get(
                f"/api/v3/vlans/{invalid_vlan_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Entry not found"
        assert response.json["message"] == f"Vlan not found: {invalid_vlan_id}"

    def test_valid(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to read a VLAN that exists
        | THEN: User should be able to read a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/vlans/{VLAN_1_REQUEST['vlan_id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == VLAN_1_RESPONSE

    def test_valid_all(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to read all VLANs
        | THEN: User should be able to read all VLANs
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/vlans",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == [VLAN_1_RESPONSE, VLAN_2_RESPONSE]


class TestUpdateVLANs:
    def test_invalid_vlan_not_found(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to update a VLAN that does not exist
        | THEN: User should not be able to update a VLAN
        """
        auth_header = auth.get_auth_header()
        invalid_vlan_id = 42
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/vlans/{invalid_vlan_id}",
                headers=auth_header,
                json=dict(),
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Vlan not found: {invalid_vlan_id}"

    def test_valid(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to update a VLAN that exists
        | THEN: User should be able to update a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/vlans/{VLAN_1_REQUEST['vlan_id']}",
                headers=auth_header,
                json=VLAN_1_UPDATE_REQUEST,
            )
        )
        assert response.status_code == 200
        assert response.json == VLAN_1_UPDATE_RESPONSE


class TestDeleteVLANs:
    def test_invalid_missing_id(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to delete a VLAN without specifying the `id` argument
        | THEN: User should not be able to delete a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/vlans",
                headers=auth_header,
            )
        )
        assert response.status_code == 404

    def test_invalid_vlan_not_found(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to delete a VLAN that does not exist
        | THEN: User should not be able to delete a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/vlans/6253",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Vlan not found: {6253}"

    def test_valid(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and VLANs from TestCreateVLANs
        | WHEN: User tries to delete a VLAN that exists
        | THEN: User should be able to delete a VLAN
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/vlans/{VLAN_2_REQUEST['vlan_id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Vlan deleted"
