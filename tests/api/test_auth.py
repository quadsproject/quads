import base64
from unittest.mock import patch

from jwt import decode
from sqlalchemy.exc import SQLAlchemyError

from tests.config import EXPIRED_TEST_TOKEN
from tests.helpers import unwrap_json

auth_token_global = ""


class TokenClassStub:
    token = ""

    def __init__(self, token):
        self.token = token

    @staticmethod
    def check_blacklist(token):
        return False


def raise_exception_stub(ignore1=None):
    raise SQLAlchemyError("Test exception.")


class UserClassStub:
    id = 0
    email = "test@redhat.com"
    password = "12345"
    active = False

    def __init__(self, id, email, password, active):
        self.id = id
        self.email = email
        self.password = password
        self.active = active

    def get_id(self):
        return self.id

    @staticmethod
    def decode_auth_token(ignore1=None):
        return "test@redhat.com"


class SQLResultStub:
    def __init__(self, result: list):
        self.result = result

    def first(self):
        return self.result[0]

    def filter(self, *ignore):
        pass


def query_stub(ignore=None):
    user = UserClassStub(1, "test@redhat.com", "password", False)
    return SQLResultStub([user])


class TestCheckAccess:
    def test_invalid_malformed_header(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint while providing a malformed auth header
        | THEN: User should not be able to access the endpoint
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Malformed"},
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Authorization header malformed"

    def test_invalid_no_token(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint without passing the auth token
        | THEN: User should not be able to access the endpoint
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing authentication data"

    def test_invalid_no_user_basic(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint as a non-existing user with basic auth
        | THEN: User should not be able to access the endpoint
        """
        credentials = base64.b64encode(b"no_user:12345").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Basic " + credentials},
            )
        )
        assert response.status_code == 401
        assert response.json["error"] == "Unauthorized"
        assert response.json["message"] == "Invalid Credentials!"

    def test_invalid_credentials(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint with basic auth and wrong password
        | THEN: User should not be able to access the endpoint
        """
        credentials = base64.b64encode(b"gonza@redhat.com:12345").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Basic " + credentials},
            )
        )
        assert response.status_code == 401
        assert response.json["error"] == "Unauthorized"
        assert response.json["message"] == "Invalid Credentials!"

    def test_invalid_wrong_role(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint with basic auth, but doesn't have the required role
        | THEN: User should not be able to access the endpoint
        """
        credentials = base64.b64encode(b"gonza@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Basic " + credentials},
            )
        )
        assert response.status_code == 403
        assert response.json["error"] == "Forbidden"
        assert response.json["message"] == "You don't have the permission to access the requested resource"

    @patch("quads.server.models.User", UserClassStub)
    def test_invalid_no_user_token(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint while passing an invalid auth token
        | THEN: User should not be able to access the endpoint
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Bearer " + "invalid_token"},
            )
        )
        assert response.status_code == 401
        assert response.json["error"] == "Unauthorized"
        assert response.json["message"] == "Invalid Authentication token!"

    @patch("quads.server.models.User", UserClassStub)
    @patch("quads.server.models.db.session")
    def test_invalid_inactive_user(self, db_session, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access an endpoint while his status is set as inactive
        | THEN: User should not be able to access the endpoint
        """
        db_session.query.return_value.filter.return_value.first.return_value = UserClassStub(
            id=1, email="test@redhat.com", password="password", active=False
        )
        response = unwrap_json(
            test_client.post(
                "/api/v3/clouds",
                json=dict(),
                headers={"Authorization": "Bearer " + auth_token_global},
            )
        )
        assert response.status_code == 403
        assert response.json["error"] == "Forbidden"
        assert response.json["message"] == "You don't have the permission to access the requested resource"


class TestRegistration:
    def test_invalid_missing(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to register with a missing email or password
        | THEN: User should not be able to register
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="not_an_email", password=""),
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Please provide both email and password."

    def test_invalid_email(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to register with an invalid email
        | THEN: User should not be able to register
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="not_an_email", password="password"),
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Invalid email address."

    def test_valid(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to register with valid email and password
        | THEN: User should be able to register
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="test_user@example.com", password="password"),
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "success"
        assert response.json["message"] == "Successfully registered"
        assert response.json["auth_token"] is not None

    def test_jwt_contains_role(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User registers with valid email and password
        | THEN: JWT token should contain role field with value "user"
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="new_test_user@example.com", password="password"),
            )
        )
        assert response.status_code == 200
        auth_token = response.json["auth_token"]
        payload = decode(auth_token, options={"verify_signature": False})
        assert "role" in payload
        assert payload["role"] == "user"
        assert payload["sub"] == "new_test_user@example.com"

    def test_existing(self, test_client):
        """
        | GIVEN: Client with test user in database
        | WHEN: User tries to register with existing email
        | THEN: User should not be able to register
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="test_user@example.com", password="password"),
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "User already exists. Please Log in."


class TestLogin:
    def test_invalid(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to log in with invalid credentials.
        | THEN: User should not be able to log in due to failed basic auth
        """
        invalid_credentials = base64.b64encode(b"none@redhat.com:wrong_password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + invalid_credentials},
            )
        )
        assert response.status_code == 401
        assert response.text == "Unauthorized Access"

    @patch("quads.server.models.User.encode_auth_token", raise_exception_stub)
    def test_invalid_exception(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to log in with valid credentials.
        | THEN: User should not be able to log in due unexpected exception
        """
        valid_credentials = base64.b64encode(b"grafuls@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        assert response.status_code == 500
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Try again"

    def test_valid(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to log in with valid email and password
        | THEN: User should be able to log in
        """
        valid_credentials = base64.b64encode(b"grafuls@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        assert response.status_code == 201
        assert response.json["status"] == "success"
        assert response.json["message"] == "Successful login"
        assert response.json["auth_token"] is not None
        global auth_token_global
        auth_token_global = response.json["auth_token"]

    def test_admin_jwt_contains_role(self, test_client):
        """
        | GIVEN: Client with admin user in database
        | WHEN: Admin user logs in
        | THEN: JWT token should contain role field with value "admin"
        """
        valid_credentials = base64.b64encode(b"grafuls@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        assert response.status_code == 201
        auth_token = response.json["auth_token"]
        payload = decode(auth_token, options={"verify_signature": False})
        assert "role" in payload
        assert payload["role"] == "admin"
        assert payload["sub"] == "grafuls@redhat.com"

    def test_user_jwt_contains_role(self, test_client):
        """
        | GIVEN: Client with regular user in database
        | WHEN: Regular user logs in
        | THEN: JWT token should contain role field with value "user"
        """
        valid_credentials = base64.b64encode(b"gonza@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        assert response.status_code == 201
        auth_token = response.json["auth_token"]
        payload = decode(auth_token, options={"verify_signature": False})
        assert "role" in payload
        assert payload["role"] == "user"
        assert payload["sub"] == "gonza@redhat.com"


class TestMe:
    def test_valid_jwt(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access /me with a valid JWT token
        | THEN: Identity and roles should be returned
        """
        valid_credentials = base64.b64encode(b"gonza@redhat.com:password").decode("utf-8")
        login_response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        auth_token = login_response.json["auth_token"]
        response = unwrap_json(
            test_client.get(
                "/api/v3/me",
                headers={"Authorization": f"Bearer {auth_token}"},
            )
        )
        assert response.status_code == 200
        assert response.json["email"] == "gonza@redhat.com"
        assert "user" in response.json["roles"]

    def test_valid_api_token(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access /me with a valid qat_ API token
        | THEN: Identity and roles should be returned
        """
        valid_credentials = base64.b64encode(b"grafuls@redhat.com:password").decode("utf-8")
        login_response = unwrap_json(
            test_client.post(
                "/api/v3/login",
                json=dict(),
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        headers = {"Authorization": "Bearer " + login_response.json["auth_token"]}
        create_response = unwrap_json(
            test_client.post(
                "/api/v3/tokens/grafuls@redhat.com/",
                json={"name": "me-test"},
                headers=headers,
            )
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/me",
                headers={"Authorization": f"Bearer {create_response.json['token']}"},
            )
        )
        assert response.status_code == 200
        assert response.json["email"] == "grafuls@redhat.com"
        assert "admin" in response.json["roles"]

    def test_invalid_no_header(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access /me without passing the auth header
        | THEN: Request should be rejected with status 400
        """
        response = unwrap_json(test_client.get("/api/v3/me"))
        assert response.status_code == 400

    def test_invalid_jwt(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access /me with an invalid JWT token
        | THEN: Request should be rejected with status 401
        """
        response = unwrap_json(
            test_client.get(
                "/api/v3/me",
                headers={"Authorization": "Bearer invalid_token"},
            )
        )
        assert response.status_code == 401

    def test_valid_basic(self, test_client):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User tries to access /me with Basic auth credentials
        | THEN: Identity should be returned
        """
        valid_credentials = base64.b64encode(b"grafuls@redhat.com:password").decode("utf-8")
        response = unwrap_json(
            test_client.get(
                "/api/v3/me",
                headers={"Authorization": "Basic " + valid_credentials},
            )
        )
        assert response.status_code == 200
        assert response.json["email"] == "grafuls@redhat.com"
        assert "admin" in response.json["roles"]


class TestLogout:
    def test_invalid_no_token(self, test_client):
        """
        | GIVEN: User logged in and in datastore
        | WHEN: User tries to log out without passing the auth token
        | THEN: User should not be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
            )
        )
        assert response.status_code == 403
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Provide a valid auth token."

    def test_invalid_wrong_token(self, test_client):
        """
        | GIVEN: User logged in and in datastore
        | WHEN: User tries to log out while passing an invalid auth token
        | THEN: User should not be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
                headers={"Authorization": "Bearer " + "invalid_token"},
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Invalid token. Please log in again."

    def test_invalid_expired_token(self, test_client):
        """
        | GIVEN: User logged in and in datastore
        | WHEN: User tries to log out while passing an expired auth token
        | THEN: User should not be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
                headers={"Authorization": "Bearer " + EXPIRED_TEST_TOKEN},
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Signature expired. Please log in again."

    def test_valid(self, test_client):
        """
        | GIVEN: Use logged in and in datastore and his valid auth token
        | WHEN: User tries to log out while passing the auth token
        | THEN: User should be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
                headers={"Authorization": "Bearer " + auth_token_global},
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "success"
        assert response.json["message"] == "Successfully logged out."

    def test_invalid_blacklisted(self, test_client):
        """
        | GIVEN: User logged in and in datastore
        | WHEN: User tries to log out while passing a blacklisted auth token
        | THEN: User should not be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
                headers={"Authorization": "Bearer " + auth_token_global},
            )
        )
        assert response.status_code == 401
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Token blacklisted. Please log in again."

    @patch("quads.server.models.TokenBlackList", TokenClassStub)
    @patch("quads.server.models.db.session.commit", raise_exception_stub)
    def test_invalid_exception(self, test_client):
        """
        | GIVEN: User logged in and in datastore
        | WHEN: User tries to log out with a valid auth token but an exception is raised (database interaction)
        | THEN: User should not be able to log out
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/logout",
                json=dict(),
                headers={"Authorization": "Bearer " + auth_token_global},
            )
        )
        assert response.status_code == 500
        assert response.json["status"] == "fail"
        assert response.json["message"] == "Test exception."
