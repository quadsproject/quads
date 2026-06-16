"""Tests for release command validation"""

from quads.server.blueprints.users import _validate_release_command


class TestValidateReleaseCommand:

    def test_valid_command(self):
        assert _validate_release_command("echo hello") is None

    def test_valid_multiline(self):
        assert _validate_release_command("echo hello\necho world") is None

    def test_empty_returns_none(self):
        assert _validate_release_command("") is None
        assert _validate_release_command(None) is None

    def test_too_long(self):
        error = _validate_release_command("x" * 1025)
        assert "1024" in error

    def test_exactly_max_length(self):
        assert _validate_release_command("x" * 1024) is None

    def test_control_chars_rejected(self):
        error = _validate_release_command("echo \x00hello")
        assert "control characters" in error

    def test_escape_char_rejected(self):
        error = _validate_release_command("echo \x1bhello")
        assert "control characters" in error

    def test_blocked_rm_rf(self):
        error = _validate_release_command("rm -rf /")
        assert "blocked" in error

    def test_blocked_rm_rf_after_semicolon(self):
        error = _validate_release_command("echo ok; rm -rf /")
        assert "blocked" in error

    def test_blocked_reboot(self):
        error = _validate_release_command("reboot")
        assert "blocked" in error

    def test_blocked_shutdown(self):
        error = _validate_release_command("shutdown -h now")
        assert "blocked" in error

    def test_blocked_fork_bomb(self):
        error = _validate_release_command(":() { :|: & } ;")
        assert "blocked" in error

    def test_blocked_dd(self):
        error = _validate_release_command("dd if=/dev/zero of=/dev/sda")
        assert "blocked" in error

    def test_blocked_mkfs(self):
        error = _validate_release_command("mkfs.ext4 /dev/sda1")
        assert "blocked" in error

    def test_blocked_init_0(self):
        error = _validate_release_command("init 0")
        assert "blocked" in error

    def test_blocked_systemctl_reboot(self):
        error = _validate_release_command("systemctl reboot")
        assert "blocked" in error

    def test_allowed_echo_reboot(self):
        assert _validate_release_command("echo reboot") is None

    def test_allowed_grep_shutdown(self):
        assert _validate_release_command("grep shutdown /var/log/messages") is None

    def test_allowed_complex_command(self):
        cmd = "source /home/user/.env ; ansible-playbook setup.yml -i hosts"
        assert _validate_release_command(cmd) is None
