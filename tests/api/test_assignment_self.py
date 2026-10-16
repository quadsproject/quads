from unittest.mock import patch

import pytest

from tests.helpers import unwrap_json

prefill_settings = ["clouds, vlans"]


class TestSelfDescriptionLimit:
    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_over_limit_rejected(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A self-assignment description exceeds ssm_description_max
        | THEN: HTTP 400 is returned and no assignment is created
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "x" * 61, "cloud": "cloud04", "ticket": "SELF-100"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Description must be 60 characters or less"

        active = unwrap_json(test_client.get("/api/v3/assignments/active/cloud04/", headers=auth_header))
        assert active.json == {}

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_limit_configurable(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with a custom ssm_description_max
        | WHEN: A self-assignment description exceeds the configured limit
        | THEN: HTTP 400 is returned with the configured limit in the message
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 5,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "abcdef", "cloud": "cloud05", "ticket": "SELF-101"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Description must be 5 characters or less"

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_non_string_rejected(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A truthy non-string description is submitted
        | THEN: HTTP 400 is returned instead of an unhandled AttributeError (500)
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": 123, "cloud": "cloud04", "ticket": "SELF-103"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid argument: description"

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_padding_not_stored(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A within-limit description is padded with whitespace
        | THEN: It passes the limit check and is stored trimmed
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "x" * 60 + " " * 100, "cloud": "cloud05", "ticket": "SELF-104"},
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["description"] == "[SSM] " + "x" * 60

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_at_limit_accepted(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A self-assignment description is exactly ssm_description_max
        | THEN: The assignment is created with the [SSM] prefix prepended
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        description = "x" * 60
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": description, "cloud": "cloud03", "ticket": "SELF-102"},
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["description"] == f"[SSM] {description}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_admin_create_description_not_limited(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds
        | WHEN: An admin creates an assignment with an over-limit description
        | THEN: The admin endpoint is not limited and returns HTTP 201
        """
        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments",
                json={
                    "description": "x" * 200,
                    "owner": "apiuser",
                    "ticket": "1",
                    "cloud": "cloud02",
                },
                headers=auth_header,
            )
        )
        assert response.status_code == 201
