import pytest

from quads.server.app import create_app
from quads.server.models import User, db


class TestModUserRole:
    def _app(self):
        return create_app("quads.server.config.TestingConfig")

    @pytest.fixture()
    def app(self, test_client):
        return self._app()

    def test_promote_user_to_admin(self, app):
        """
        | GIVEN: an existing regular user
        | WHEN: mod-user is run with --role admin
        | THEN: the user's role is replaced with admin
        """
        with app.app_context():
            before = db.session.query(User).filter(User.email == "regularuser@example.com").first()
            assert [role.name for role in before.roles] == ["user"]

        result = app.test_cli_runner().invoke(
            args=["mod-user", "--username", "regularuser@example.com", "--role", "admin"]
        )
        assert result.exit_code == 0
        assert "Role updated to admin" in result.output

        with app.app_context():
            user = db.session.query(User).filter(User.email == "regularuser@example.com").first()
            assert [role.name for role in user.roles] == ["admin"]

    def test_unknown_role_rejected(self, app):
        """
        | GIVEN: an existing user
        | WHEN: mod-user is run with an unknown role
        | THEN: the role is not changed and an error is printed
        """
        result = app.test_cli_runner().invoke(
            args=["mod-user", "--username", "apiuser@example.com", "--role", "superuser"]
        )
        assert result.exit_code == 0
        assert "Role superuser not found" in result.output

        with app.app_context():
            user = db.session.query(User).filter(User.email == "apiuser@example.com").first()
            assert [role.name for role in user.roles] == ["admin"]
