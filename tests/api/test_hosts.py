from datetime import datetime
from unittest.mock import patch

import pytest

from tests.config import HOST_1_REQUEST, HOST_2_REQUEST
from tests.helpers import unwrap_json

prefill_settings = ["clouds"]


class TestCreateHosts:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_model(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with missing model argument
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        del host_request["model"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: model"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_model(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with undefined model in the Quads config
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["model"] = "R999"
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Model R999 does not seem to be part of the defined models on quads.yml"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_name(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with missing name argument
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        del host_request["name"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: name"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_host_type(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with missing host_type argument
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        del host_request["host_type"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: host_type"

    @patch("quads.config.Config.spare_pool_name", None)
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_default_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with missing default_cloud argument and no spare pool cloud defined
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        del host_request["default_cloud"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: default_cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_default_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host with an undefined cloud
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["default_cloud"] = "cloudDoesNotExist"
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Default Cloud not found: {host_request['default_cloud']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_multi(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new hosts
        | THEN: User should be able to create a new hosts
        """
        auth_header = auth.get_auth_header()
        for num, req in enumerate([HOST_1_REQUEST, HOST_2_REQUEST], start=1):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/hosts",
                    json=req,
                    headers=auth_header,
                )
            )
            assert response.status_code == 200
            assert response.json["id"] == num
            assert response.json["name"] == req["name"]
            assert response.json["model"] == req["model"].upper()
            assert response.json["host_type"] == req["host_type"]
            assert response.json["default_cloud_id"] == response.json["cloud_id"]
            duration = datetime.utcnow() - datetime.strptime(response.json["created_at"], "%a, %d %b %Y %H:%M:%S GMT")
            assert duration.total_seconds() < 5

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_already_exists(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds
        | WHEN: User tries to create a new host that already exists
        | THEN: User should not be able to create a new host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/hosts",
                json=HOST_1_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host {HOST_1_REQUEST['name']} already exists"


class TestGetHosts:
    # QUERY HOSTS BY HOSTNAME [quads.server.blueprints.hosts.get_host()]
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_by_hostname(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by its hostname
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f'/api/v3/hosts/{HOST_1_REQUEST["name"]}',
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["id"] == 1
        assert response.json["name"] == HOST_1_REQUEST["name"]
        assert response.json["model"] == HOST_1_REQUEST["model"].upper()
        assert response.json["host_type"] == HOST_1_REQUEST["host_type"]
        assert response.json["default_cloud_id"] == response.json["cloud_id"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by hostname that does not exist
        | THEN: User should not be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts/hostDoesNotExist",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Host not found: hostDoesNotExist"

    # QUERY HOSTS WITH FILTERS [quads.server.blueprints.hosts.get_hosts()]
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_filter_by_model(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by model
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f'/api/v3/hosts?model={HOST_1_REQUEST["model"].upper()}',
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 1
        assert response.json[0]["id"] == 1
        assert response.json[0]["name"] == HOST_1_REQUEST["name"]
        assert response.json[0]["model"] == HOST_1_REQUEST["model"].upper()
        assert response.json[0]["host_type"] == HOST_1_REQUEST["host_type"]
        assert response.json[0]["default_cloud_id"] == response.json[0]["cloud_id"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_filter_by_boolean(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by boolean, search for not
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts?broken=False",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 2
        assert response.json[0]["id"] == 1
        assert response.json[0]["name"] == HOST_1_REQUEST["name"]
        assert response.json[0]["model"] == HOST_1_REQUEST["model"].upper()
        assert response.json[0]["host_type"] == HOST_1_REQUEST["host_type"]
        assert response.json[0]["default_cloud_id"] == response.json[0]["cloud_id"]
        assert response.json[1]["id"] == 2
        assert response.json[1]["name"] == HOST_2_REQUEST["name"]
        assert response.json[1]["model"] == HOST_2_REQUEST["model"].upper()
        assert response.json[1]["host_type"] == HOST_2_REQUEST["host_type"]
        assert response.json[1]["default_cloud_id"] == response.json[1]["cloud_id"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_filter_alias(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get hosts that have different host_type than "scalelab" (not equal to)
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts?host_type__ne=scalelab",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 1
        assert response.json[0]["id"] == 2
        assert response.json[0]["name"] == HOST_2_REQUEST["name"]
        assert response.json[0]["model"] == HOST_2_REQUEST["model"].upper()
        assert response.json[0]["host_type"] == HOST_2_REQUEST["host_type"]
        assert response.json[0]["default_cloud_id"] == response.json[0]["cloud_id"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_group_by(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get hosts that have different host_type than "scalelab" (not equal to)
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts?group_by=model",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) == 2
        assert response.json.get("FC640") == 1
        assert response.json.get("R640") == 1

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_group_by_bad(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get hosts that have different host_type than "scalelab" (not equal to)
        | THEN: User should be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts?group_by=bad",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "bad is not a valid field."

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_filter_by_undefined_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by cloud that does not exist
        | THEN: User should not be able to get the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/hosts?cloud=cloudDoesNotExist",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Cloud not found: cloudDoesNotExist"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_filter_too_many_args(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host with too many arguments
        | THEN: User should not be able to get the host
        """
        auth_header = auth.get_auth_header()
        too_many_args_filter = "cloud.last_redefined.date=2023-01-01"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts?{too_many_args_filter}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Too many arguments: {too_many_args_filter.split('=')[0].split('.')}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_filter_by_invalid_field(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to get a host by invalid field
        | THEN: User should not be able to get the host
        """
        auth_header = auth.get_auth_header()
        invalid_field_filter = "invalid_field=true"
        response = unwrap_json(
            test_client.get(
                f"/api/v3/hosts?{invalid_field_filter}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"{invalid_field_filter.split('=')[0]} is not a valid field."


class TestUpdateHosts:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_update_host_type(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to update a host with a new host_type
        | THEN: User should be able to update the host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["host_type"] = "alias"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/hosts/{host_request['name']}",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["id"] == 1
        assert response.json["name"] == host_request["name"]
        assert response.json["model"] == host_request["model"]
        assert response.json["host_type"] == host_request["host_type"]
        assert response.json["default_cloud_id"] == response.json["cloud_id"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to update a host that does not exist
        | THEN: User should not be able to update the host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["host_type"] = "alias"
        undefined_host = "undefinedHost"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/hosts/{undefined_host}",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {undefined_host}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_default_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to update a host to an undefined default cloud
        | THEN: User should not be able to update the host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["default_cloud"] = "undefinedCloud"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/hosts/{host_request['name']}",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {host_request['default_cloud']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to update a host to an undefined cloud
        | THEN: User should not be able to update the host
        """
        auth_header = auth.get_auth_header()
        host_request = HOST_1_REQUEST.copy()
        host_request["cloud"] = "undefinedCloud"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/hosts/{host_request['name']}",
                json=host_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {host_request['cloud']}"


class TestDeleteHosts:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to delete a host
        | THEN: User should be able to delete the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/hosts/{HOST_1_REQUEST['name']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Host deleted"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_undefined_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth token and clouds and hosts from TestCreateHosts
        | WHEN: User tries to delete a host that does not exist
        | THEN: User should not be able to delete the host
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/hosts/{HOST_1_REQUEST['name']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {HOST_1_REQUEST['name']}"
