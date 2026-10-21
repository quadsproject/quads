"""Tests for the shared Rich console factory (issue #754)."""

from quads.helpers.console import make_console


def test_make_console_disables_emoji_substitution():
    console = make_console()

    with console.capture() as capture:
        console.print("04:32:01:ab:62:f1")

    output = capture.get()
    assert "\U0001F18E" not in output
    assert "04:32:01:ab:62:f1" in output


def test_make_console_cannot_reenable_emoji():
    console = make_console(emoji=True)

    with console.capture() as capture:
        console.print("04:32:01:ab:62:f1")

    assert "\U0001F18E" not in capture.get()
