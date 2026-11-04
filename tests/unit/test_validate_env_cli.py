from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from quads.cli import QuadsCli


def _cli(quads, cli_args=None):
    cli = QuadsCli(quads=quads, logger=MagicMock())
    cli.cli_args = cli_args or {}
    return cli


@pytest.mark.asyncio
async def test_run_validation_does_not_mark_provisioned():
    """validate-env must not infer provisioned from stale host.validated flags.

    M&R owns that transition (abd2a198). Inferring it here validates an
    environment while it is still being rebuilt and sends false failures.
    """
    stale_assignment = MagicMock(id=7)
    stale_assignment.cloud.name = "cloud02"
    quads = MagicMock()

    def filter_assignments(filters):
        if filters.get("provisioned") is False:
            return [stale_assignment]
        return []

    quads.filter_assignments.side_effect = filter_assignments
    quads.get_current_schedules.return_value = [MagicMock(host=MagicMock(validated=True))]

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=(True, ""))

    with patch("quads.cli.cli.get_validator_dispatcher", return_value=validator):
        await _cli(quads)._run_validation()

    quads.update_assignment.assert_not_called()
    validator.validate.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_validation_validates_provisioned_assignments():
    """Assignments M&R marked provisioned are still validated."""
    assignment = MagicMock()
    assignment.cloud.name = "cloud02"
    active_assignment = MagicMock(wipe=True)
    quads = MagicMock()

    def filter_assignments(filters):
        return [assignment] if filters.get("provisioned") is True else []

    quads.filter_assignments.side_effect = filter_assignments
    quads.get_current_schedules.return_value = [MagicMock()]
    quads.get_active_cloud_assignment.return_value = active_assignment
    quads.filter_hosts.return_value = []

    validator = MagicMock()
    validator.validate = AsyncMock(return_value=(True, ""))

    with patch("quads.cli.cli.get_validator_dispatcher", return_value=validator):
        await _cli(quads)._run_validation()

    validator.validate.assert_awaited_once_with("cloud02", active_assignment, [], None, None)
