from unittest.mock import Mock

import pytest
from requests import Response

from quads.config import Config
from quads.quads_api import QuadsApi


@pytest.fixture
def api():
    client = QuadsApi(Config)
    client.session = Mock()
    return client


def test_update_notification_sends_flags_to_notification_id(api):
    data = {"fail": False, "success": True}
    response = Mock(spec=Response, status_code=200)
    api.session.patch.return_value = response

    assert api.update_notification(42, data) is response
    api.session.patch.assert_called_once_with(
        f"{api.base_url}/notifications/42", json=data, verify=False, auth=api.auth
    )
