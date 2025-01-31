from datetime import datetime

from tests.helpers import unwrap_json


class TestCreateClouds:
    def test_valid(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and user logged in
        | WHEN: User tries to create a cloud with valid data, loop 10 times
        | THEN: User should be able to create a cloud
        """
        auth_header = auth.get_auth_header()
        for cloud_id in range(1, 11):
            cloud_name = f"cloud{str(cloud_id).zfill(2)}"
            response = unwrap_json(
                test_client.post(
                    "/api/v3/clouds",
                    json=dict(cloud=cloud_name),
                    headers=auth_header,
                )
            )
            assert response.status_code == 201
            assert response.json["id"] == cloud_id
            assert response.json["name"] == cloud_name
            duration = datetime.utcnow() - datetime.strptime(
                response.json["last_redefined"], "%a, %d %b %Y %H:%M:%S GMT"
            )
            assert duration.total_seconds() < 5

    def test_invalid_missing_arg(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and user logged in
        | WHEN: User tries to create a cloud with missing name
        | THEN: User should not be able to create a cloud
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: cloud"

    def test_invalid_exists(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to create a cloud with already an existing cloud using the same name
        | THEN: User should not be able to create a cloud
        """
        auth_header = auth.get_auth_header()
        cloud_name = "cloud01"
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(cloud=cloud_name),
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud {cloud_name} already exists"


class TestReadClouds:
    def test_valid_single(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to read a cloud with valid id
        | THEN: User should be able to read a cloud
        """
        auth_header = auth.get_auth_header()
        cloud_id = 1
        cloud_name = f"cloud{str(cloud_id).zfill(2)}"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/clouds?name={cloud_name}",
                headers=auth_header,
            )
        )
        cloud = response.json[0]
        assert response.status_code == 200
        assert cloud["id"] == cloud_id
        assert cloud["name"] == cloud_name
        assert cloud["last_redefined"] is not None

    def test_valid_multiple(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to read all clouds
        | THEN: User should be able to read all clouds
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/clouds",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 10
        for cloud_id in range(1, 11):
            cloud_name = f"cloud{str(cloud_id).zfill(2)}"
            assert response.json[cloud_id - 1]["id"] == cloud_id
            assert response.json[cloud_id - 1]["name"] == cloud_name
            assert response.json[cloud_id - 1]["last_redefined"] is not None

    def test_free_cloud(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to read all free clouds
        | THEN: User should be able to read all free clouds
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/clouds/free/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 9
        for cloud_id in range(2, 11):
            cloud_name = f"cloud{str(cloud_id).zfill(2)}"
            assert response.json[cloud_id - 2]["id"] == cloud_id
            assert response.json[cloud_id - 2]["name"] == cloud_name
            assert response.json[cloud_id - 2]["last_redefined"] is not None

    def test_invalid_not_found_single(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to read a cloud with invalid id
        | THEN: User should not be able to read a cloud
        """
        auth_header = auth.get_auth_header()
        cloud_name = "cloud11"
        response = unwrap_json(test_client.get(f"/api/v3/clouds?name={cloud_name}", headers=auth_header))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "No clouds found with the given filters"

    def test_invalid_filter(self, test_client, auth):
        """
        | GIVEN: Clouds from TestCreateClouds in database and user logged in
        | WHEN: User tries to filter clouds with invalid filter
        | THEN: User should not be able to filter clouds
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(test_client.get("/api/v3/clouds?NOT_A_FIELD=invalid", headers=auth_header))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "NOT_A_FIELD is not a valid field."

    def test_valid_filter(self, test_client, auth):
        """
        | GIVEN: Clouds from TestCreateClouds in database and user logged in
        | WHEN: User tries to filter clouds with valid filter
        | THEN: User should be able to filter clouds
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(test_client.get("/api/v3/clouds?id=1", headers=auth_header))
        assert response.status_code == 200
        assert len(response.json) == 1
        assert response.json[0]["id"] == 1
        assert response.json[0]["name"] == "cloud01"
        assert response.json[0]["last_redefined"] is not None


class TestDeleteClouds:
    def test_valid(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to delete a cloud with valid id
        | THEN: User should be able to delete a cloud
        """
        auth_header = auth.get_auth_header()
        cloud_id = 1
        cloud_name = f"cloud{str(cloud_id).zfill(2)}"
        response = unwrap_json(test_client.delete(f"/api/v3/clouds/{cloud_name}", headers=auth_header))
        assert response.status_code == 204

    def test_invalid_missing_arg(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to delete a cloud while passing no name argument
        | THEN: User should not be able to delete a cloud
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(test_client.delete("/api/v3/clouds/", headers=auth_header))
        assert response.status_code == 405

    def test_invalid_cloud_not_found(self, test_client, auth):
        """
        | GIVEN: Clouds from test_valid in database and user logged in
        | WHEN: User tries to delete a cloud with id that doesn't match any cloud
        | THEN: User should not be able to delete a cloud
        """
        auth_header = auth.get_auth_header()
        cloud_name = "cloud11"
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/clouds/{cloud_name}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {cloud_name}"
