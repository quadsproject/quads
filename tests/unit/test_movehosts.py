from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.cli import QuadsCli
from quads.exceptions import CliException
from quads.quads_api import APIServerException

MOVE = {"host": "host1.example.com", "current": "cloud01", "new": "cloud02"}


def _run_movehosts(
    quads_setup=None,
    cli_args=None,
    configure=None,
    move_and_rebuild=None,
    conf_get=None,
    from_dict_return=None,
):
    """Drive action_movehosts with a fully mocked QuadsApi and dispatchers.

    Defaults model the single-host happy path (one cloud, one host, switch
    configure succeeds). Pass quads_setup(quads) to tweak the QuadsApi mock for
    a specific branch. Returns a namespace with the mocks for assertions.
    """
    configure = configure or AsyncMock(return_value=True)
    switch_dispatcher = MagicMock(configure=configure)

    move_and_rebuild = move_and_rebuild or AsyncMock(return_value=True)
    release_dispatcher = MagicMock(move_and_rebuild=move_and_rebuild)

    quads = MagicMock()
    quads.get_moves.return_value = [dict(MOVE)]
    quads.get_active_cloud_assignment.return_value = None
    quads.get_host.return_value = MagicMock(switch_config_applied=False)
    quads.start_move_batch.return_value.json.return_value = {MOVE["host"]: 1}
    quads.get_current_schedules.return_value = [MagicMock()]
    if quads_setup:
        quads_setup(quads)

    cli = QuadsCli(quads=quads, logger=MagicMock())
    cli.cli_args = cli_args or {"datearg": None, "dryrun": False}

    with (
        patch("quads.cli.cli.get_switch_dispatcher", return_value=switch_dispatcher),
        patch("quads.cli.cli.get_release_dispatcher", return_value=release_dispatcher),
        patch("quads.cli.cli.foreman_heal") as foreman_heal,
        patch("quads.cli.cli.conf") as conf_mock,
        patch("quads.cli.cli.Assignment") as assignment_cls,
    ):
        conf_mock.get.side_effect = conf_get or (lambda *a, **k: None)
        assignment_cls.return_value.from_dict.return_value = (
            from_dict_return if from_dict_return is not None else MagicMock(wipe=False)
        )
        rc = cli.action_movehosts()

    return SimpleNamespace(
        rc=rc,
        quads=quads,
        configure=configure,
        move_and_rebuild=move_and_rebuild,
        foreman_heal=foreman_heal,
        logger=cli.logger,
    )


def _applied_true_calls(quads):
    return [
        call
        for call in quads.update_host.call_args_list
        if len(call.args) > 1 and call.args[1].get("switch_config_applied") is True
    ]


def test_movehosts_awaits_switch_configure():
    """The async switch configure must actually be awaited, not left as a
    dangling coroutine, and the flag flips True only on a real success."""
    ns = _run_movehosts()

    ns.configure.assert_awaited_once_with("host1.example.com", "cloud01", "cloud02")
    ns.quads.update_host.assert_any_call("host1.example.com", {"switch_config_applied": True})


def test_movehosts_holds_flag_when_switch_config_fails():
    """A failed switch change must leave switch_config_applied False so the
    environment is held back instead of released with an unconfigured switch."""
    ns = _run_movehosts(configure=AsyncMock(return_value=False))

    ns.configure.assert_awaited_once()
    assert not _applied_true_calls(ns.quads), "switch_config_applied must stay False when switch config fails"


def test_movehosts_switch_configure_exception_holds_flag():
    """An exception from switch configure marks the move failed and must not
    flip switch_config_applied."""
    ns = _run_movehosts(configure=AsyncMock(side_effect=Exception("boom")))

    ns.configure.assert_awaited_once()
    assert not _applied_true_calls(ns.quads)
    ns.quads.update_move_status.assert_any_call(
        1, {"status": "failed", "error_message": "Switch configuration failed"}
    )


def test_movehosts_omit_network_move_skips_switch():
    """Hosts/clouds in omit_network_move must skip switch configuration."""
    ns = _run_movehosts(conf_get=lambda key=None, *a, **k: "cloud02" if key == "omit_network_move" else None)

    ns.configure.assert_not_awaited()
    assert not _applied_true_calls(ns.quads)


def test_movehosts_date_without_dryrun_raises():
    """--move-hosts with --date but no --dry-run is rejected."""
    cli = QuadsCli(quads=MagicMock(), logger=MagicMock())
    cli.cli_args = {"datearg": "2026-01-01 00:00", "dryrun": False}
    with pytest.raises(CliException):
        cli.action_movehosts()


def test_movehosts_dryrun_with_date_noop():
    """Dry-run with a date and nothing to move returns cleanly without
    touching assignment reconciliation."""
    ns = _run_movehosts(
        quads_setup=lambda q: setattr(q.get_moves, "return_value", []),
        cli_args={"datearg": "2026-01-01 00:00", "dryrun": True},
    )

    assert ns.rc == 0
    ns.quads.get_active_assignments.assert_not_called()


def _no_moves_assignment(build):
    def setup(q):
        q.get_moves.return_value = []
        assignment = MagicMock(provisioned=False, wipe=False, id=5)
        assignment.cloud.name = "cloud02"
        q.get_active_assignments.return_value = [assignment]
        q.get_host.return_value = MagicMock(build=build)

    return setup


def test_movehosts_nothing_to_do_marks_provisioned():
    """With no moves, an assignment whose hosts are all built is marked
    provisioned."""
    ns = _run_movehosts(
        quads_setup=_no_moves_assignment(build=True),
        conf_get=lambda key=None, *a, **k: "cloud01" if key == "spare_pool_name" else None,
    )

    ns.quads.update_assignment.assert_any_call(5, {"provisioned": True, "validated": True})
    ns.foreman_heal.assert_called_once()


def test_movehosts_nothing_to_do_partial_unbuilt():
    """An assignment with an unbuilt host is not marked provisioned."""
    ns = _run_movehosts(
        quads_setup=_no_moves_assignment(build=False),
        conf_get=lambda key=None, *a, **k: "cloud01" if key == "spare_pool_name" else None,
    )

    ns.quads.update_assignment.assert_not_called()
    ns.foreman_heal.assert_not_called()


def test_movehosts_nothing_to_do_api_error_is_logged():
    """An API error during the no-moves reconciliation is logged, not raised."""

    def setup(q):
        q.get_moves.return_value = []
        q.get_active_assignments.side_effect = APIServerException("boom")

    ns = _run_movehosts(quads_setup=setup)

    assert ns.rc == 0
    assert ns.logger.error.called


def test_movehosts_success_marks_assignment_and_deactivates_old_cloud():
    """A successful non-wipe move marks the new assignment provisioned and
    validated, and deactivates an emptied old cloud."""

    def setup(q):
        q.get_moves.return_value = [{"host": "host1.example.com", "current": "cloud03", "new": "cloud02"}]
        q.get_active_cloud_assignment.return_value = MagicMock(wipe=False, id=42)
        q.get_current_schedules.return_value = []

    ns = _run_movehosts(quads_setup=setup, from_dict_return=MagicMock(wipe=False))

    ns.quads.update_assignment.assert_any_call(42, {"active": False})
    ns.quads.update_assignment.assert_any_call(42, {"provisioned": True, "validated": True})
    ns.quads.update_move_status.assert_any_call(1, {"status": "released", "message": "Environment released"})
    ns.quads.update_move_status.assert_any_call(1, {"status": "completed"})


def test_movehosts_wipe_invalidates_assignment():
    """A wipe move with an active schedule invalidates the assignment and does
    not auto-validate it after provisioning."""

    def setup(q):
        q.get_active_cloud_assignment.return_value = MagicMock(wipe=True, id=7)
        q.get_current_schedules.return_value = [MagicMock()]

    ns = _run_movehosts(quads_setup=setup, from_dict_return=MagicMock(wipe=True))

    ns.quads.update_assignment.assert_any_call(7, {"validated": False})
    ns.quads.update_assignment.assert_any_call(7, {"provisioned": True, "validated": False})


def test_movehosts_start_move_batch_failure_is_logged():
    """A failed start_move_batch is logged and the switch config still runs."""
    ns = _run_movehosts(quads_setup=lambda q: setattr(q.start_move_batch, "side_effect", Exception("db down")))

    assert ns.logger.warning.called
    ns.configure.assert_awaited_once()
    ns.quads.update_host.assert_any_call("host1.example.com", {"switch_config_applied": True})


def test_movehosts_move_failure_skips_provisioning():
    """A move_and_rebuild failure is caught and the assignment is not marked
    provisioned."""
    ns = _run_movehosts(move_and_rebuild=AsyncMock(side_effect=Exception("fail")))

    ns.logger.exception.assert_any_call("Move command failed")
    ns.quads.update_assignment.assert_not_called()
