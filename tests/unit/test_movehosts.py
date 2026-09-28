from unittest.mock import AsyncMock, MagicMock, patch

from quads.cli import QuadsCli

MOVE = {"host": "host1.example.com", "current": "cloud01", "new": "cloud02"}


def _run_movehosts(configure_return):
    """Drive action_movehosts with a fully mocked QuadsApi and dispatchers.

    Returns (configure_mock, quads_mock) for assertions on the switch step.
    """
    configure = AsyncMock(return_value=configure_return)
    switch_dispatcher = MagicMock()
    switch_dispatcher.configure = configure

    release_dispatcher = MagicMock()
    release_dispatcher.move_and_rebuild = AsyncMock(return_value=True)

    quads = MagicMock()
    quads.get_moves.return_value = [dict(MOVE)]
    quads.get_active_cloud_assignment.return_value = None
    quads.get_host.return_value = MagicMock(switch_config_applied=False)
    quads.start_move_batch.return_value.json.return_value = {MOVE["host"]: 1}

    cli = QuadsCli(quads=quads, logger=MagicMock())
    cli.cli_args = {"datearg": None, "dryrun": False}

    with (
        patch("quads.cli.cli.get_switch_dispatcher", return_value=switch_dispatcher),
        patch("quads.cli.cli.get_release_dispatcher", return_value=release_dispatcher),
        patch("quads.cli.cli.foreman_heal"),
        patch("quads.cli.cli.conf") as conf_mock,
    ):
        conf_mock.get.return_value = None
        cli.action_movehosts()

    return configure, quads


def test_movehosts_awaits_switch_configure():
    """The async switch configure must actually be awaited, not left as a
    dangling coroutine, and the flag flips True only on a real success."""
    configure, quads = _run_movehosts(configure_return=True)

    configure.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")
    quads.update_host.assert_any_call("host1.example.com", {"switch_config_applied": True})


def test_movehosts_holds_flag_when_switch_config_fails():
    """A failed switch change must leave switch_config_applied False so the
    environment is held back instead of released with an unconfigured switch."""
    configure, quads = _run_movehosts(configure_return=False)

    configure.assert_awaited_once()
    applied_true = [
        call
        for call in quads.update_host.call_args_list
        if len(call.args) > 1 and call.args[1].get("switch_config_applied") is True
    ]
    assert not applied_true, "switch_config_applied must stay False when switch config fails"
