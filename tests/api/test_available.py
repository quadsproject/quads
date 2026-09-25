from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlencode

import pytest

from quads.config import Config
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

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_start_at_boundary(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User checks availability for a range starting exactly when a schedule ends
        | THEN: The answer matches the schedule creation check (no minute of the range is skipped)
        """
        auth_header = auth.get_auth_header()
        base = {"cloud": "cloud02", "hostname": "host5.example.com"}
        first = {
            **base,
            "start": "2099-01-05 00:00",
            "end": "2099-01-05 10:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=first,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        # Block the first minute after the boundary so an off-by-one start shift is observable.
        second = {
            **base,
            "start": "2099-01-05 10:00",
            "end": "2099-01-05 10:01",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=second,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        req = {"start": "2099-01-05T10:00", "end": "2099-01-05T12:00"}
        api_resp = unwrap_json(
            test_client.get(
                f"/api/v3/available/host5.example.com?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert api_resp.status_code == 200
        assert api_resp.json == {"host5.example.com": "False"}

        req["start"] = "2099-01-05T10:01"
        api_resp = unwrap_json(
            test_client.get(
                f"/api/v3/available/host5.example.com?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert api_resp.status_code == 200
        assert api_resp.json == {"host5.example.com": "True"}

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_zero_length_at_boundary(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User checks availability for the exact instant a schedule ends
        | THEN: A point query at instant T answers only against schedules covering T
        """
        auth_header = auth.get_auth_header()
        base = {"cloud": "cloud02"}
        # host4: schedule ends exactly at 2099-01-06 10:00 -> released at 10:00
        schedule = {**base, "hostname": "host4.example.com", "start": "2099-01-06 00:00", "end": "2099-01-06 10:00"}
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        # host5: back-to-back schedule starts at 10:00 -> occupied at 10:00
        schedule = {**base, "hostname": "host5.example.com", "start": "2099-01-06 00:00", "end": "2099-01-06 10:00"}
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        schedule = {**base, "hostname": "host5.example.com", "start": "2099-01-06 10:00", "end": "2099-01-06 10:01"}
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        req = {"start": "2099-01-06T10:00", "end": "2099-01-06T10:00"}
        api_resp = unwrap_json(
            test_client.get(
                f"/api/v3/available/host4.example.com?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert api_resp.status_code == 200
        assert api_resp.json == {"host4.example.com": "True"}
        api_resp = unwrap_json(
            test_client.get(
                f"/api/v3/available/host5.example.com?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert api_resp.status_code == 200
        assert api_resp.json == {"host5.example.com": "False"}

        req = {"start": "2099-01-06T10:01", "end": "2099-01-06T10:01"}
        api_resp = unwrap_json(
            test_client.get(
                f"/api/v3/available/host5.example.com?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert api_resp.status_code == 200
        assert api_resp.json == {"host5.example.com": "True"}


class TestAvailableInvalidInput:
    def test_invalid_host_date(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User checks host availability with a malformed date
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/available/host1.example.com?start=bogus"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"


class TestAvailableSsmModelLimit:
    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts, self_assignments"], indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.available.datetime")
    def test_ssm_model_limit_caps_available(
        self, mock_datetime_available, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Two free same-model hosts and a 50% per-model limit (N=2, L=1)
        | WHEN: Available hosts are queried with can_self_schedule=true
        | THEN: Only one host of the capped model is listed; other views are uncapped
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R660": 50}, raising=False)
        auth_header = auth.get_auth_header()
        for name in ("host901.example.com", "host902.example.com"):
            test_client.post(
                "/api/v3/hosts",
                json={
                    "name": name,
                    "default_cloud": "cloud04",
                    "model": "r660",
                    "rack": "h99",
                    "uloc": "u99",
                    "host_type": "scalelab",
                },
                headers=auth_header,
            )

        now = datetime(2080, 7, 1, 12, 0, 0)
        mock_datetime_available.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(test_client.get("/api/v3/available?can_self_schedule=true"))
        assert response.status_code == 200
        assert "host901.example.com" in response.json
        assert "host902.example.com" not in response.json

        response = unwrap_json(test_client.get("/api/v3/available"))
        assert "host901.example.com" in response.json
        assert "host902.example.com" in response.json

        monkeypatch.setattr(Config, "ssm_model_limit", {"R660": 0}, raising=False)
        response = unwrap_json(test_client.get("/api/v3/available?can_self_schedule=true"))
        assert "host901.example.com" not in response.json
        assert "host902.example.com" not in response.json
