import json
from unittest.mock import patch, MagicMock

from tests.helpers import unwrap_json


class TestPasswordRecovery:
    """Test cases for password recovery API endpoint"""

    def test_reset_password_missing_email(self, test_client):
        """Test password reset without providing email"""
        response = unwrap_json(
            test_client.post(
                "/api/v3/resetpassword/",
                json={},
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Email address is required."

    def test_reset_password_invalid_email(self, test_client):
        """Test password reset with invalid email format"""
        response = unwrap_json(
            test_client.post(
                "/api/v3/resetpassword/",
                json={"email": "invalid-email"},
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Invalid email address."

    def test_reset_password_valid_email(self, test_client):
        """Test password reset with valid email"""
        with patch("quads.server.blueprints.auth.user_datastore") as mock_datastore:
            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_datastore.find_user.return_value = mock_user

            response = unwrap_json(
                test_client.post(
                    "/api/v3/resetpassword/",
                    json={"email": "test@example.com"},
                    headers={"Content-Type": "application/json"},
                )
            )

            assert response.status_code == 200
            assert response.json["status"] == "success"
            assert "password reset link has been sent" in response.json["message"]
            assert "reset_token" in response.json  # This would be removed in production

    def test_reset_password_nonexistent_user(self, test_client):
        """Test password reset for non-existent user"""
        with patch("quads.server.blueprints.auth.user_datastore") as mock_datastore:
            mock_datastore.find_user.return_value = None

            response = unwrap_json(
                test_client.post(
                    "/api/v3/resetpassword/",
                    json={"email": "nonexistent@example.com"},
                    headers={"Content-Type": "application/json"},
                )
            )

            # Should return success for security (don't reveal if user exists)
            assert response.status_code == 200
            assert response.json["status"] == "success"
            assert "password reset link has been sent" in response.json["message"]

    def test_reset_password_exception(self, test_client):
        """Test password reset when exception occurs"""
        with patch("quads.server.blueprints.auth.user_datastore") as mock_datastore:
            mock_datastore.find_user.side_effect = Exception("Database error")

            response = unwrap_json(
                test_client.post(
                    "/api/v3/resetpassword/",
                    json={"email": "test@example.com"},
                    headers={"Content-Type": "application/json"},
                )
            )

            assert response.status_code == 500
            assert response.json["status"] == "fail"
            assert response.json["message"] == "Error processing password reset request."
