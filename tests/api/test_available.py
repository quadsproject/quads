from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytest

from tests.helpers import unwrap_json

prefill_settings = ["clouds, vlans, hosts, assignments, schedules"]


class TestReadAvailable:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_filter(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User tries to read the currently available hosts (by dates and by current assigned cloud)
        | THEN: User should be able to get the available host(s) for each case
        """
        auth_header = auth.get_auth_header()
        start_date = datetime.now() + timedelta(weeks=1)
        start_str = start_date.strftime("%Y-%m-%d")
        start_date_future = start_date + timedelta(days=3651)
        start_str_future = start_date_future.strftime("%Y-%m-%d")
        end_date = start_date + timedelta(days=3652)
        end_str = end_date.strftime("%Y-%m-%d")
        requests = [
            {"start": f"{start_str}T00:00"},
            {"start": f"{start_str_future}T00:00", "end": f"{end_str}T22:00"},
            {"start": f"{start_str_future}T00:00", "cloud": "cloud02"},
        ]
        responses = [
            [
                "host1.example.com",
                "host4.example.com",
                "host5.example.com",
            ],
            ["host1.example.com", "host2.example.com", "host4.example.com", "host5.example.com"],
            ["host2.example.com"],
        ]
        for i, (req, resp) in enumerate(zip(requests, responses)):
            api_resp = unwrap_json(
                test_client.get(
                    f"/api/v3/available?{urlencode(req)}",
                    headers=auth_header,
                )
            )
            assert api_resp.status_code == 200
            assert api_resp.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_is_available(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User tries to verify if a host is/will be available for a given date range
        | THEN: User should be able to get an answer if it is or isn't
        """
        auth_header = auth.get_auth_header()
        start_date = datetime.now() + timedelta(weeks=1)
        start_str = start_date.strftime("%Y-%m-%d")
        start_date_future = start_date + timedelta(days=3651)
        start_str_future = start_date_future.strftime("%Y-%m-%d")
        end_date = start_date + timedelta(days=3652)
        end_str = end_date.strftime("%Y-%m-%d")
        hostname = "host2.example.com"
        responses = [
            {hostname: "True"},
            {hostname: "False"},
        ]
        requests = [
            {"start": f"{start_str_future}T00:00"},
            {"start": f"{start_str}T00:00", "end": f"{end_str}T00:00"},
        ]
        for i, (req, resp) in enumerate(zip(requests, responses)):
            api_resp = unwrap_json(
                test_client.get(
                    f"/api/v3/available/{hostname}?{urlencode(req)}",
                    headers=auth_header,
                )
            )
            assert api_resp.status_code == 200
            assert api_resp.json == resp
