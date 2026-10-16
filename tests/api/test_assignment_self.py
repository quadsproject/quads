from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.helpers import unwrap_json

prefill_settings = ["clouds, vlans"]


class TestSelfDescriptionLimit:
    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_over_limit_truncated(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A self-assignment description exceeds ssm_description_max
        | THEN: It is truncated to the limit and an assignment is created
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
        assert response.status_code == 201
        assert response.json["description"] == "[SSM] " + "x" * 60
        assert response.json["warning"] == "description truncated, maximum 60 characters"

        active = unwrap_json(test_client.get("/api/v3/assignments/active/cloud04/", headers=auth_header))
        assert active.json["description"] == "[SSM] " + "x" * 60

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_limit_configurable_truncates(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with a custom ssm_description_max
        | WHEN: A self-assignment description exceeds the configured limit
        | THEN: It is truncated to the configured limit and an assignment is created
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
        assert response.status_code == 201
        assert response.json["description"] == "[SSM] abcde"
        assert response.json["warning"] == "description truncated, maximum 5 characters"

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("bad_max", [0, -1, "60", None, True])
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_limit_invalid_config_uses_default(self, mock_config_get, test_client, auth, prefill, bad_max):
        """
        | GIVEN: Defaults, auth, clouds with an invalid ssm_description_max
        | WHEN: A self-assignment description exceeds the default limit
        | THEN: The default limit is used and the description is truncated to it
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": bad_max,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "x" * 61, "cloud": "cloud04", "ticket": "SELF-106"},
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["description"] == "[SSM] " + "x" * 60
        assert response.json["warning"] == "description truncated, maximum 60 characters"

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

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
    def test_description_whitespace_only_rejected(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with self-scheduling enabled
        | WHEN: A whitespace-only description is submitted
        | THEN: HTTP 400 is returned as if the description were missing
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
        active_before = unwrap_json(test_client.get("/api/v3/assignments/active/", headers=auth_header))
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "   ", "cloud": "cloud04", "ticket": "SELF-105"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: description"

        active_after = unwrap_json(test_client.get("/api/v3/assignments/active/", headers=auth_header))
        assert len(active_after.json) == len(active_before.json)

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

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

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
        assert "warning" not in response.json

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

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
        assert response.json["description"] == "x" * 200

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_custom_prefix_excluded(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with a custom ssm_description_prefix
        | WHEN: A self-assignment description is exactly the limit
        | THEN: The prefix does not count toward the limit and is prepended
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[X]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": False,
        }.get(key, default)

        auth_header = auth.get_auth_header("apiuser@example.com")
        response = unwrap_json(
            test_client.post(
                "/api/v3/assignments/self/",
                json={"description": "x" * 60, "cloud": "cloud05", "ticket": "SELF-109"},
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["description"] == "[X] " + "x" * 60
        assert "warning" not in response.json

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200

    @patch("quads.server.blueprints.assignments.Config.get")
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_description_truncated_jira_ticket_summary(self, mock_config_get, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds with automatic JIRA ticket creation enabled
        | WHEN: A self-assignment description is truncated
        | THEN: The ticket summary uses the truncated value and the warning is returned
        """
        mock_config_get.side_effect = lambda key, default=None: {
            "ssm_enable": True,
            "ssm_user_cloud_limit": 10,
            "spare_pool_name": "cloud01",
            "ssm_description_prefix": "[SSM]",
            "ssm_description_max": 60,
            "ssm_jira_create_ticket": True,
        }.get(key, default)

        dispatcher = MagicMock()
        dispatcher.create_ticket = AsyncMock(return_value="TICKET-1")
        mock_app = MagicMock()
        mock_app.extensions.get.return_value = {"ticketing": dispatcher}

        auth_header = auth.get_auth_header("apiuser@example.com")
        with patch("quads.server.blueprints.assignments.current_app", mock_app):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/assignments/self/",
                    json={"description": "x" * 61, "cloud": "cloud04", "ticket": "SELF-108"},
                    headers=auth_header,
                )
            )
        assert response.status_code == 201
        assert response.json["description"] == "[SSM] " + "x" * 60
        assert response.json["warning"] == "description truncated, maximum 60 characters"
        dispatcher.create_ticket.assert_awaited_once()
        assert dispatcher.create_ticket.await_args.kwargs["summary"] == "[SSM] " + "x" * 60

        deleted = unwrap_json(test_client.delete(f"/api/v3/assignments/{response.json['id']}/", headers=auth_header))
        assert deleted.status_code == 200
