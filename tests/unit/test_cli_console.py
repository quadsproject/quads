"""Tests for the CLI's Rich console configuration (issue #754)."""

from unittest.mock import MagicMock

from quads.cli import QuadsCli


def test_cli_console_does_not_substitute_emoji_shortcodes():
    """Table cells hold raw data: a MAC octet like ':ab:' must not become an emoji."""
    cli = QuadsCli(quads=MagicMock(), logger=MagicMock())

    with cli.console.capture() as capture:
        cli.console.print("04:32:01:ab:62:f1")

    output = capture.get()
    assert "\U0001F18E" not in output
    assert "04:32:01:ab:62:f1" in output
