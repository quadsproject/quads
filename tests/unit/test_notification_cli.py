from unittest.mock import Mock

import pytest
from requests import Response

from quads.cli import QuadsCli
from quads.exceptions import CliException
from quads.quads_api import APIBadRequest, APIServerException, QuadsApi
from quads.server.models import Assignment, Cloud, Notification


@pytest.fixture
def api():
    client = Mock(spec=QuadsApi)
    client.get_active_cloud_assignment.return_value = Assignment(
        id=7,
        cloud=Cloud(name="cloud02"),
        ticket="1234",
        notification=Notification(id=42, assignment_id=7),
    )
    return client


@pytest.mark.parametrize("flags", [{"fail": "true", "success": "false"}, {"fail": False, "success": True}])
def test_modify_notification_uses_notification_id(api, flags, capsys):
    api.update_notification.return_value = Mock(spec=Response, status_code=200)
    cli = QuadsCli(quads=api, logger=Mock())

    cli.run("modify_notification", {"cloud": "cloud02", "initial": None, **flags})

    api.update_notification.assert_called_once_with(notification_id=42, data=flags)
    api.get_active_cloud_assignment.assert_called_with(cloud_name="cloud02")
    assert "cloud02" in capsys.readouterr().out


@pytest.mark.parametrize(
    "error",
    [APIServerException("Check the flask server logs"), APIBadRequest("Invalid notification flag")],
    ids=["server-error", "bad-request"],
)
def test_modify_notification_wraps_update_errors(api, error, capsys):
    api.update_notification.side_effect = error
    logger = Mock()
    cli = QuadsCli(quads=api, logger=logger)

    with pytest.raises(CliException) as exc_info:
        cli.run("modify_notification", {"cloud": "cloud02", "fail": False})

    assert str(exc_info.value) == str(error)
    api.update_notification.assert_called_once_with(notification_id=42, data={"fail": False})
    api.get_active_cloud_assignment.assert_called_once_with(cloud_name="cloud02")
    logger.info.assert_not_called()
    assert capsys.readouterr().out == ""
