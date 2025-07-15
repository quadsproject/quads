from unittest.mock import patch, MagicMock

import pytest

from quads.exceptions import CliException
from quads.server.dao.user import UserDao
from quads.server.models import User, Role
from tests.cli.test_base import TestBase


class TestUserManagement(TestBase):
    """Test cases for user management CLI commands"""

    def setup_method(self):
        """Reset cli_args before each test"""
        self.cli_args = {"datearg": None, "filter": None, "force": "False"}

    def test_ls_users(self):
        """Test listing all users"""
        with patch.object(UserDao, "get_users") as mock_get_users:
            # Mock a user with roles
            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_user.active = True
            mock_role = MagicMock(spec=Role)
            mock_role.name = "admin"
            mock_user.roles = [mock_role]

            mock_get_users.return_value = [mock_user]

            self.quads_cli_call("ls_users")

            assert "Users:" in self._caplog.messages[0]
            assert "test@example.com (active) - roles: admin" in self._caplog.messages[1]

    def test_ls_users_no_users(self):
        """Test listing users when none exist"""
        with patch.object(UserDao, "get_users") as mock_get_users:
            mock_get_users.return_value = []

            self.quads_cli_call("ls_users")

            assert "No users found" in self._caplog.messages[0]

    def test_rm_user_missing_user_arg(self):
        """Test removing user without providing user email"""
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("rm_user")

        assert "Missing option. --user option is required for --rm-user." in str(ex.value)

    def test_rm_user_user_not_found(self):
        """Test removing non-existent user"""
        self.cli_args["user"] = "nonexistent@example.com"

        with patch.object(UserDao, "get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(CliException) as ex:
                self.quads_cli_call("rm_user")

            assert "User not found: nonexistent@example.com" in str(ex.value)

    def test_rm_user_success(self):
        """Test successful user removal"""
        self.cli_args["user"] = "test@example.com"

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch.object(UserDao, "delete_user") as mock_delete_user,
            patch("quads.cli.cli.QuadsCli._confirmation_dialog") as mock_confirm,
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user
            mock_delete_user.return_value = True
            mock_confirm.return_value = True

            self.quads_cli_call("rm_user")

            assert "User deleted: test@example.com" in self._caplog.messages[0]

    def test_rm_user_cancelled(self):
        """Test user removal cancellation"""
        self.cli_args["user"] = "test@example.com"

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch("quads.cli.cli.QuadsCli._confirmation_dialog") as mock_confirm,
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user
            mock_confirm.return_value = False

            self.quads_cli_call("rm_user")

            assert "User deletion cancelled" in self._caplog.messages[0]

    def test_mod_user_missing_user_arg(self):
        """Test modifying user without providing user email"""
        with pytest.raises(CliException) as ex:
            self.quads_cli_call("mod_user")

        assert "Missing option. --user option is required for --mod-user." in str(ex.value)

    def test_mod_user_user_not_found(self):
        """Test modifying non-existent user"""
        self.cli_args["user"] = "nonexistent@example.com"

        with patch.object(UserDao, "get_user") as mock_get_user:
            mock_get_user.return_value = None

            with pytest.raises(CliException) as ex:
                self.quads_cli_call("mod_user")

            assert "User not found: nonexistent@example.com" in str(ex.value)

    def test_mod_user_set_password(self):
        """Test setting user password"""
        self.cli_args["user"] = "test@example.com"
        self.cli_args["set_password"] = "newpassword123"

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch.object(UserDao, "change_user_password") as mock_change_password,
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user
            mock_change_password.return_value = True

            self.quads_cli_call("mod_user")

            assert "Password reset for test@example.com" in self._caplog.messages[0]

    def test_mod_user_prompt_password_mismatch(self):
        """Test password prompt with mismatched passwords"""
        self.cli_args["user"] = "test@example.com"
        self.cli_args["prompt_password"] = True

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch("getpass.getpass", side_effect=["password1", "password2"]),
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user

            with pytest.raises(CliException) as ex:
                self.quads_cli_call("mod_user")

            assert "Passwords do not match" in str(ex.value)

    def test_mod_user_change_email(self):
        """Test changing user email"""
        self.cli_args["user"] = "test@example.com"
        self.cli_args["user_email"] = "newemail@example.com"

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch.object(UserDao, "change_user_email") as mock_change_email,
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user
            mock_change_email.return_value = True

            self.quads_cli_call("mod_user")

            assert "Email changed from test@example.com to newemail@example.com" in self._caplog.messages[0]

    def test_mod_user_set_active_status(self):
        """Test setting user active status"""
        self.cli_args["user"] = "test@example.com"
        self.cli_args["user_active"] = "false"

        with (
            patch.object(UserDao, "get_user") as mock_get_user,
            patch.object(UserDao, "set_user_active") as mock_set_active,
        ):

            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user
            mock_set_active.return_value = True

            self.quads_cli_call("mod_user")

            assert "User test@example.com set to inactive" in self._caplog.messages[0]

    def test_mod_user_show_info(self):
        """Test showing user info when no modifications are requested"""
        self.cli_args["user"] = "test@example.com"

        with patch.object(UserDao, "get_user") as mock_get_user:
            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_user.active = True
            mock_role = MagicMock(spec=Role)
            mock_role.name = "admin"
            mock_user.roles = [mock_role]
            mock_get_user.return_value = mock_user

            self.quads_cli_call("mod_user")

            assert "User: test@example.com" in self._caplog.messages[0]
            assert "Status: active" in self._caplog.messages[1]
            assert "Roles: admin" in self._caplog.messages[2]

    def test_mod_user_conflicting_password_args(self):
        """Test using both set-password and prompt-password together"""
        self.cli_args["user"] = "test@example.com"
        self.cli_args["set_password"] = "newpassword123"
        self.cli_args["prompt_password"] = True

        with patch.object(UserDao, "get_user") as mock_get_user:
            mock_user = MagicMock(spec=User)
            mock_user.email = "test@example.com"
            mock_get_user.return_value = mock_user

            with pytest.raises(CliException) as ex:
                self.quads_cli_call("mod_user")

            assert "Cannot use both --set-password and --prompt-password together." in str(ex.value)
