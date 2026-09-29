from unittest.mock import Mock

import pytest
from requests import Response

from quads.cli import QuadsCli
from quads.quads_api import QuadsApi
from quads.server.models import Assignment, Cloud, Notification


@pytest.mark.parametrize("flags", [{"fail": "true", "success": "false"}, {"fail": False, "success": True}])
def test_modify_notification_uses_notification_id(flags, capsys):
    api = Mock(spec=QuadsApi)
    api.get_active_cloud_assignment.return_value = Assignment(
        id=7,
        cloud=Cloud(name="cloud02"),
        ticket="1234",
        notification=Notification(id=42, assignment_id=7),
    )
    api.update_notification.return_value = Mock(spec=Response, status_code=200)
    cli = QuadsCli(quads=api, logger=Mock())

    cli.run("modify_notification", {"cloud": "cloud02", "initial": None, **flags})

    api.update_notification.assert_called_once_with(notification_id=42, data=flags)
    api.get_active_cloud_assignment.assert_called_with(cloud_name="cloud02")
    assert "cloud02" in capsys.readouterr().out
