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
        with (
            patch("quads.server.blueprints.auth.user_datastore") as mock_datastore,
            patch("quads.server.blueprints.auth.Postman") as mock_postman,
        ):

            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_user.id = 1
            mock_datastore.find_user.return_value = mock_user

            # Mock successful email sending
            mock_postman_instance = MagicMock()
            mock_postman_instance.send_email.return_value = True
            mock_postman.return_value = mock_postman_instance

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
            assert "reset_token" not in response.json  # Should not be in production

    def test_reset_password_email_failure(self, test_client):
        """Test password reset when email sending fails"""
        with (
            patch("quads.server.blueprints.auth.user_datastore") as mock_datastore,
            patch("quads.server.blueprints.auth.Postman") as mock_postman,
        ):

            mock_user = MagicMock()
            mock_user.email = "test@example.com"
            mock_user.id = 1
            mock_datastore.find_user.return_value = mock_user

            # Mock failed email sending
            mock_postman_instance = MagicMock()
            mock_postman_instance.send_email.return_value = False
            mock_postman.return_value = mock_postman_instance

            response = unwrap_json(
                test_client.post(
                    "/api/v3/resetpassword/",
                    json={"email": "test@example.com"},
                    headers={"Content-Type": "application/json"},
                )
            )

            assert response.status_code == 500
            assert response.json["status"] == "fail"
            assert response.json["message"] == "Error sending password reset email."

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

    def test_confirm_reset_password_missing_params(self, test_client):
        """Test password confirmation without required parameters"""
        response = unwrap_json(
            test_client.post(
                "/api/v3/confirmresetpassword/",
                json={"token": "some_token"},  # Missing password
                headers={"Content-Type": "application/json"},
            )
        )

        assert response.status_code == 400
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Reset token and new password are required."

    def test_confirm_reset_password_invalid_token(self, test_client):
        """Test password confirmation with invalid token"""
        with patch("quads.server.blueprints.auth.db") as mock_db:
            mock_db.session.query.return_value.filter_by.return_value.first.return_value = None

            response = unwrap_json(
                test_client.post(
                    "/api/v3/confirmresetpassword/",
                    json={"token": "invalid_token", "password": "newpassword123"},
                    headers={"Content-Type": "application/json"},
                )
            )

            assert response.status_code == 400
            assert response.json["status"] == "fail"
            assert response.json["message"] == "Invalid or expired reset token."

    def test_confirm_reset_password_valid_token(self, test_client):
        """Test password confirmation with valid token"""
        with patch("quads.server.blueprints.auth.db") as mock_db:
            mock_token = MagicMock()
            mock_token.is_valid.return_value = True
            mock_user = MagicMock()
            mock_token.user = mock_user

            mock_db.session.query.return_value.filter_by.return_value.first.return_value = mock_token

            response = unwrap_json(
                test_client.post(
                    "/api/v3/confirmresetpassword/",
                    json={"token": "valid_token", "password": "newpassword123"},
                    headers={"Content-Type": "application/json"},
                )
            )

            assert response.status_code == 200
            assert response.json["status"] == "success"
            assert response.json["message"] == "Password has been reset successfully."
            assert mock_token.used == True
