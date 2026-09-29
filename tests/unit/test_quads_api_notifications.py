from unittest.mock import Mock

import pytest
from requests import Response

from quads.config import Config
from quads.quads_api import APIBadRequest, APIServerException, QuadsApi
from quads.server.models import Notification


@pytest.fixture
def api():
    client = QuadsApi(Config)
    client.session = Mock()
    return client


@pytest.fixture(
    params=[
        ("get_notification", 42, "notifications/42"),
        ("get_assignment_notification", 7, "notifications/assignment/7"),
    ]
)
def lookup(request):
    return request.param


def test_get_notification_deserializes_flags(api, lookup):
    method, resource_id, endpoint = lookup
    data = {
        "id": 42,
        "assignment_id": 7,
        "fail": False,
        "success": True,
        "initial": True,
        "pre_initial": False,
        "pre": True,
        "one_day": False,
        "three_days": True,
        "five_days": False,
        "seven_days": True,
    }
    api.session.get.return_value = Mock(spec=Response, status_code=200)
    api.session.get.return_value.json.return_value = data

    notification = getattr(api, method)(resource_id)

    assert isinstance(notification, Notification)
    assert notification.as_dict() == data
    api.session.get.assert_called_once_with(f"{api.base_url}/{endpoint}", verify=False, auth=api.auth)


@pytest.mark.parametrize("data", [None, {}])
def test_empty_notification_returns_none(api, lookup, data):
    method, resource_id, _ = lookup
    api.session.get.return_value = Mock(spec=Response, status_code=200)
    api.session.get.return_value.json.return_value = data

    assert getattr(api, method)(resource_id) is None


@pytest.mark.parametrize(
    "status_code,exception,message",
    [
        (400, APIBadRequest, "Notification not found"),
        (500, APIServerException, "Check the flask server logs"),
    ],
)
def test_notification_lookup_propagates_api_errors(api, lookup, status_code, exception, message):
    method, resource_id, _ = lookup
    api.session.get.return_value = Mock(spec=Response, status_code=status_code)
    api.session.get.return_value.json.return_value = {"message": message}

    with pytest.raises(exception, match=message):
        getattr(api, method)(resource_id)


def test_update_notification_sends_flags_to_notification_id(api):
    data = {"fail": False, "success": True}
    response = Mock(spec=Response, status_code=200)
    api.session.patch.return_value = response

    assert api.update_notification(42, data) is response
    api.session.patch.assert_called_once_with(
        f"{api.base_url}/notifications/42", json=data, verify=False, auth=api.auth
    )
