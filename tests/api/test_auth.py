import base64
from unittest.mock import patch

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
                json=dict(email="test_user@redhat.com", password="password"),
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "success"
        assert response.json["message"] == "Successfully registered"
        assert response.json["auth_token"] is not None

    def test_existing(self, test_client):
        """
        | GIVEN: Client with test user in database
        | WHEN: User tries to register with existing email
        | THEN: User should not be able to register
        """
        response = unwrap_json(
            test_client.post(
                "/api/v3/register",
                json=dict(email="test_user@redhat.com", password="password"),
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
        assert response.status_code == 200
        assert response.json["status"] == "success"
        assert response.json["message"] == "Successful login"
        assert response.json["auth_token"] is not None
        global auth_token_global
        auth_token_global = response.json["auth_token"]


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
