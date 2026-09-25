from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from urllib.parse import urlencode

import pytest

from quads.config import Config
from quads.helpers.timeutil import ensure_utc, parse_datetime, parse_http_date
from tests.config import (
    SCHEDULE_1_REQUEST,
    SCHEDULE_1_RESPONSE,
    SCHEDULE_1_UPDATE_REQUEST,
    SCHEDULE_2_REQUEST,
    SCHEDULE_2_RESPONSE,
    SELF_SCHEDULE_1_REQUEST,
    SELF_SCHEDULE_1_RESPONSE,
    SELF_SCHEDULE_2_REQUEST,
    SELF_SCHEDULE_2_RESPONSE,
    SELF_SCHEDULE_3_REQUEST,
    SELF_SCHEDULE_NON_REQUEST,
    end_str,
    start_str,
)
from tests.helpers import unwrap_json
from quads.server.blueprints.schedules import _trigger_jira_notification
from quads.server.dao.assignment import AssignmentDao
from quads.server.dao.baseDao import InvalidArgument, SQLError
from quads.server.dao.host import HostDao
from quads.server.dao.schedule import ScheduleDao
from quads.server.models import db

prefill_settings = ["clouds, vlans, hosts, assignments"]
prefill_schedule = ["clouds, vlans, hosts, assignments, schedules"]
prefill_self_schedule = ["clouds, vlans, hosts, self_assignments"]
prefill_self_non_schedule = ["clouds, vlans, non_self_hosts, self_assignments"]


def _create_host(test_client, auth_header, name, model="r660"):
    return unwrap_json(
        test_client.post(
            "/api/v3/hosts",
            json={
                "name": name,
                "default_cloud": "cloud04",
                "model": model,
                "rack": "h99",
                "uloc": "u99",
                "host_type": "scalelab",
            },
            headers=auth_header,
        )
    )


class TestCreateSchedule:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule without specifying a cloud
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        del schedule_request["cloud"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule for a non-existent cloud
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["cloud"] = "invalid_cloud"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {schedule_request['cloud']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_no_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule for a cloud without an active assignment
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["cloud"] = "cloud05"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"No active assignment for cloud: {schedule_request['cloud']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_hostname(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule without specifying a hostname
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        del schedule_request["hostname"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: hostname"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_hostname_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule for a non-existent hostname
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["hostname"] = "invalid_hostname"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {schedule_request['hostname']}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_not_available(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule for a host that is not available
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()

        conflicting_schedule = SCHEDULE_1_REQUEST.copy()
        conflicting_schedule["hostname"] = "host1.example.com"
        conflicting_schedule["cloud"] = "cloud02"
        test_client.post(
            "/api/v3/schedules",
            json=conflicting_schedule,
            headers=auth_header,
        )

        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["hostname"] = "host1.example.com"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Host is not available for the specified date range"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_date(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule without specifying start or end date
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        del schedule_request["start"]
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Missing argument: start or end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_format(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule with an invalid date format
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["start"] = "invalid_date"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date format for start or end, correct format: 'YYYY-MM-DD HH:MM'"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule with an invalid date range
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["start"] = "2020-01-01 00:00"
        schedule_request["end"] = "2019-01-01 00:00"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule with valid data
        | THEN: User should be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_requests = [SCHEDULE_1_REQUEST.copy(), SCHEDULE_2_REQUEST.copy()]
        schedule_responses = [SCHEDULE_1_RESPONSE.copy(), SCHEDULE_2_RESPONSE.copy()]
        schedule_requests[1]["start"] = (datetime.now() + timedelta(6 * 30)).strftime("%Y-%m-%d %H:%M")
        for req, resp in zip(schedule_requests, schedule_responses):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules",
                    json=req,
                    headers=auth_header,
                )
            )
            resp["assignment"]["cloud"]["last_redefined"] = response.json["assignment"]["cloud"]["last_redefined"]
            resp["assignment"]["created_at"] = response.json["assignment"]["created_at"]
            resp["created_at"] = response.json["created_at"]
            resp["host"]["created_at"] = response.json["host"]["created_at"]
            resp["host"]["cloud"]["last_redefined"] = response.json["host"]["cloud"]["last_redefined"]
            resp["host"]["default_cloud"]["last_redefined"] = response.json["host"]["default_cloud"]["last_redefined"]
            resp["start"] = response.json["start"]
            resp["end"] = response.json["end"]
            resp["id"] = response.json["id"]
            assert response.status_code == 201
            assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_zero_length_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule with start equal to end
        | THEN: User should not be able to create a zero-length schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["start"] = "2099-06-01 12:00"
        schedule_request["end"] = "2099-06-01 12:00"
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_back_to_back(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User schedules a host for a range starting exactly when an existing schedule ends
        | THEN: The back-to-back schedule is created (half-open [start, end) boundaries)
        """
        auth_header = auth.get_auth_header()
        base = {"cloud": "cloud02", "hostname": "host4.example.com"}
        first = {
            **base,
            "start": "2099-01-02 00:00",
            "end": "2099-01-02 08:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=first,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        second = {
            **base,
            "start": "2099-01-02 08:00",
            "end": "2099-01-02 12:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=second,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self(self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule with valid data
        | THEN: User should be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host5.example.com"

        now = datetime(2080, 5, 8, 18, 40, 38)
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self_limit(self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User creates multiple self schedules
        | THEN: User should be able to create schedules up to the limit
        """
        auth_header = auth.get_auth_header()

        now = datetime(2080, 5, 8, 18, 40, 38)
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        # Create schedules for different hosts under same cloud/assignment
        hostnames = ["host1.example.com", "host2.example.com"]
        for hostname in hostnames:
            req = SELF_SCHEDULE_1_REQUEST.copy()
            req["hostname"] = hostname
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules",
                    json=req,
                    headers=auth_header,
                )
            )
            assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self_string_deadline_hour(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and self_assignments
        | WHEN: User self-schedules on the deadline day with a string ssm_deadline_hour
        | THEN: The schedule is created instead of a TypeError from replace(hour=<str>)
        """
        monkeypatch.setattr(Config, "ssm_deadline_hour", "21")
        monkeypatch.setattr(Config, "ssm_host_limit", 1000)
        monkeypatch.setattr("quads.server.dao.schedule.ScheduleDao.is_host_available", lambda *a, **k: True)
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host3.example.com"

        now = datetime(2080, 5, 12, 18, 40, 38)  # Sunday: deadline day, days_ahead == 0
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_invalid_self_deadline_passed(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and self_assignments
        | WHEN: User self-schedules at 22:00 on the deadline day with a 21:00 deadline
        | THEN: The request is rejected with a 400 because the deadline window has passed
        """
        monkeypatch.setattr(Config, "ssm_host_limit", 1000)
        monkeypatch.setattr("quads.server.dao.schedule.ScheduleDao.is_host_available", lambda *a, **k: True)
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host1.example.com"

        now = datetime(2080, 5, 12, 22, 0, 0)  # Sunday 22:00, deadline hour 21:00
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Self-schedule deadline has already passed for today"

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self_string_default_lifetime(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and self_assignments
        | WHEN: ssm_default_lifetime is a string from config
        | THEN: The schedule is created instead of a TypeError from int/str comparison
        """
        monkeypatch.setattr(Config, "ssm_default_lifetime", "1")
        monkeypatch.setattr(Config, "ssm_host_limit", 1000)
        monkeypatch.setattr("quads.server.dao.schedule.ScheduleDao.is_host_available", lambda *a, **k: True)
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host4.example.com"

        now = datetime(2080, 5, 12, 18, 40, 38)  # Sunday: deadline day, days_ahead == 0
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self_weekday_deadline_wraps_to_next(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and self_assignments
        | WHEN: A weekday ssm_deadline_day has already passed this week
        | THEN: the end date is the NEXT deadline window, not start + lifetime
        """
        monkeypatch.setattr(Config, "ssm_deadline_day", "wednesday")
        monkeypatch.setattr(Config, "ssm_deadline_hour", "21")
        monkeypatch.setattr(Config, "ssm_default_lifetime", "5")
        monkeypatch.setattr(Config, "ssm_host_limit", 1000)
        monkeypatch.setattr("quads.server.dao.schedule.ScheduleDao.is_host_available", lambda *a, **k: True)
        monkeypatch.setattr(
            "quads.server.dao.schedule.ScheduleDao.count_ss_schedules_by_model_overlap",
            lambda *a, **k: 0,
        )
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host3.example.com"

        now = datetime(2080, 5, 12, 20, 0, 0)  # Sunday; target Wednesday already passed
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        print("WEEKDAY RESP:", response.status_code, response.json.get("message"))
        assert response.status_code == 201

        end_dt = parsedate_to_datetime(response.json["end"]).replace(tzinfo=None)
        assert end_dt.date() == datetime(2080, 5, 15).date()  # next Wednesday

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self_fractional_lifetime_keeps_deadline(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and self_assignments
        | WHEN: ssm_default_lifetime is a fractional float (e.g. 1.5)
        | THEN: it is not truncated; the deadline window branch is still taken
        """
        monkeypatch.setattr(Config, "ssm_deadline_day", "monday")
        monkeypatch.setattr(Config, "ssm_deadline_hour", "21")
        monkeypatch.setattr(Config, "ssm_default_lifetime", 1.5)
        monkeypatch.setattr(Config, "ssm_host_limit", 1000)
        monkeypatch.setattr("quads.server.dao.schedule.ScheduleDao.is_host_available", lambda *a, **k: True)
        monkeypatch.setattr(
            "quads.server.dao.schedule.ScheduleDao.count_ss_schedules_by_model_overlap",
            lambda *a, **k: 0,
        )
        auth_header = auth.get_auth_header()
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host4.example.com"

        now = datetime(2080, 5, 12, 20, 0, 0)  # Sunday; target Monday is next week (days_ahead 1)
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        print("FRACTIONAL RESP:", response.status_code, response.json.get("message"))
        assert response.status_code == 201

        start_dt = parsedate_to_datetime(response.json["start"]).replace(tzinfo=None)
        end_dt = parsedate_to_datetime(response.json["end"]).replace(tzinfo=None)
        # 1.5 lifetime with days_ahead 1 -> deadline window (Mon 21:00) = 25h,
        # not the int-truncated fallback (Mon 20:00) = 24h
        assert end_dt - start_dt == timedelta(hours=25)

    @pytest.mark.parametrize("prefill", prefill_self_non_schedule, indirect=True)
    def test_invalid_self_schedule_non(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule for a non-self-schedulable host
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_request = SELF_SCHEDULE_NON_REQUEST.copy()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host {schedule_request['hostname']} is not allowed to self-schedule"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_now_keyword(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User creates a schedule with 'now' as start date
        | THEN: Schedule should be created with current datetime
        """
        auth_header = auth.get_auth_header()
        schedule_request = SCHEDULE_1_REQUEST.copy()
        schedule_request["hostname"] = "host5.example.com"
        schedule_request["start"] = "now"
        schedule_request["end"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        start_time = parsedate_to_datetime(response.json["start"]).replace(tzinfo=None)
        now = datetime.now()
        assert abs((start_time - now).total_seconds()) < 60

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_ssm_model_limit_first_create_ok_second_rejected(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Two new same-model hosts and a 50% per-model limit (N=2, L=1)
        | WHEN: A user self-schedules both hosts
        | THEN: The first is created and the second is rejected by the model limit
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R660": 50}, raising=False)
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host101.example.com")
        _create_host(test_client, auth_header, "host102.example.com")
        now = datetime(2080, 7, 1, 12, 0, 0)
        mock_datetime_schedules.now.return_value = now
        mock_datetime_dao.now.return_value = now

        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host101.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 201

        req["hostname"] = "host102.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 400
        assert response.json["message"] == "Model R660 has reached its self-scheduling limit"

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_ssm_model_limit_zero_disables_model(self, test_client, auth, prefill, monkeypatch):
        """
        | GIVEN: A model with a 0% self-scheduling limit
        | WHEN: A user tries to self-schedule a host of that model
        | THEN: The request is rejected before availability is considered
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R650": 0}, raising=False)
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host201.example.com", model="r650")

        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host201.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 400
        assert response.json["message"] == "Model R650 has reached its self-scheduling limit"

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_ssm_model_limit_default_hundred_unlimited(self, test_client, auth, prefill):
        """
        | GIVEN: No per-model limit configured (default 100)
        | WHEN: A user self-schedules two hosts of the same model
        | THEN: Both are created (no regression)
        """
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host301.example.com", model="r630")
        _create_host(test_client, auth_header, "host302.example.com", model="r630")

        for hostname in ("host301.example.com", "host302.example.com"):
            req = SELF_SCHEDULE_1_REQUEST.copy()
            req["hostname"] = hostname
            response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
            assert response.status_code == 201

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_ssm_model_limit_batch_rejects_overflow(self, test_client, auth, prefill, monkeypatch):
        """
        | GIVEN: A self-schedule assignment with a 50% per-model limit (L=1)
        | WHEN: An admin batch-schedules two same-model hosts
        | THEN: The whole batch is rejected with the model limit message
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R760": 50}, raising=False)
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host401.example.com", model="r760")
        _create_host(test_client, auth_header, "host402.example.com", model="r760")

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json={
                    "cloud": "cloud04",
                    "hostnames": ["host401.example.com", "host402.example.com"],
                    "start": "2080-07-20 12:00",
                    "end": "2080-07-27 12:00",
                },
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Model R760 has reached its self-scheduling limit"

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.dao.schedule.datetime")
    @patch("quads.server.blueprints.schedules.datetime")
    def test_ssm_model_limit_patch_window_rejected(
        self, mock_datetime_schedules, mock_datetime_dao, test_client, auth, prefill, monkeypatch
    ):
        """
        | GIVEN: Two same-model hosts self-scheduled in non-overlapping windows (L=1)
        | WHEN: The first schedule's end is pushed to overlap the second
        | THEN: The PATCH is rejected by the model limit
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R620": 50}, raising=False)
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host501.example.com", model="r620")
        _create_host(test_client, auth_header, "host502.example.com", model="r620")

        mock_datetime_schedules.now.return_value = datetime(2080, 7, 1, 12, 0, 0)
        mock_datetime_dao.now.return_value = datetime(2080, 7, 1, 12, 0, 0)
        mock_datetime_schedules.strptime.side_effect = datetime.strptime
        mock_datetime_dao.strptime.side_effect = datetime.strptime
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host501.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 201
        schedule_id = response.json["id"]

        mock_datetime_schedules.now.return_value = datetime(2080, 7, 7, 12, 0, 0)
        mock_datetime_dao.now.return_value = datetime(2080, 7, 7, 12, 0, 0)
        req["hostname"] = "host502.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 201

        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{schedule_id}",
                json={"end": "2080-07-13T12:00"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Model R620 has reached its self-scheduling limit"

        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{schedule_id}",
                json={"end": "2080-07-02T12:00"},
                headers=auth_header,
            )
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_ssm_model_limit_floor_disables_tiny_fleet(self, test_client, auth, prefill, monkeypatch):
        """
        | GIVEN: A one-host model with a 50% limit (L=0 on purpose)
        | WHEN: A user tries to self-schedule that host
        | THEN: The request is rejected (floor edge pinned)
        """
        monkeypatch.setattr(Config, "ssm_model_limit", {"R6625": 50}, raising=False)
        auth_header = auth.get_auth_header()
        _create_host(test_client, auth_header, "host601.example.com", model="r6625")
        req = SELF_SCHEDULE_1_REQUEST.copy()
        req["hostname"] = "host601.example.com"
        response = unwrap_json(test_client.post("/api/v3/schedules", json=req, headers=auth_header))
        assert response.status_code == 400
        assert response.json["message"] == "Model R6625 has reached its self-scheduling limit"


class TestGetSchedules:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get all schedules
        | THEN: User should be able to get all schedules
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) >= 2

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_filter_bad_request(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get schedules with invalid filter
        | THEN: User should not be able to get schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"nonexistent_filter": "invalid_value"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_filter_entry_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get schedules with non-existent filter value
        | THEN: User should not be able to get schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"cloud": "nonexistent_cloud"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_single(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get a single schedule by ID
        | THEN: User should be able to get the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["id"] == SCHEDULE_1_RESPONSE["id"]

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_single_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get a non-existent schedule by ID
        | THEN: User should not be able to get the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules/999",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Schedule not found: 999"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_current(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get current schedules
        | THEN: User should be able to get current schedules
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules/current",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) >= 0

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_current_at_exact_end(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User asks for the current schedule at the exact moment a schedule ends
        | THEN: The schedule is no longer current (half-open [start, end) boundaries)
        """
        auth_header = auth.get_auth_header()
        req = {
            "cloud": "cloud02",
            "hostname": "host5.example.com",
            "start": "2099-01-08 00:00",
            "end": "2099-01-08 10:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=req,
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        url = "/api/v3/schedules/current?host=host5.example.com&date=2099-01-08T10:00"
        response = unwrap_json(test_client.get(url, headers=auth_header))
        assert response.status_code == 200
        assert response.json == []

        url = "/api/v3/schedules/current?host=host5.example.com&date=2099-01-08T09:00"
        response = unwrap_json(test_client.get(url, headers=auth_header))
        assert response.status_code == 200
        assert len(response.json) == 1

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_current_filter_date(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get current schedules with date filter
        | THEN: User should be able to get current schedules
        """
        auth_header = auth.get_auth_header()
        date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
        filters = {"date": date}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/current?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) >= 0

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_current_filter_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get current schedules with host filter
        | THEN: User should be able to get current schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"host": "host2.example.com"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/current?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) >= 0

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_current_filter_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get current schedules with cloud filter
        | THEN: User should be able to get current schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"cloud": "cloud02"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/current?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert len(response.json) >= 0

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_filter(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to filter schedules by host
        | THEN: User should be able to get schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"host": "host2.example.com"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        for schedule in response.json:
            assert schedule["host"]["name"] == "host2.example.com"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_filter_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to filter schedules by assignment
        | THEN: User should be able to get schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"assignment_id": "1"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        for schedule in response.json:
            assert schedule["assignment"]["id"] == 1
        for schedule in response.json:
            assert schedule["assignment"]["cloud"]["name"] == "cloud02"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_future(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get future schedules
        | THEN: User should be able to get future schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"host": "host2.example.com", "cloud": "cloud02"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/future?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid_hosts_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to get hosts within a date range
        | THEN: User should be able to get hosts
        """
        auth_header = auth.get_auth_header()
        start = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M")
        end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d %H:%M")
        filters = {"start": start, "end": end}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/hosts_range?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert isinstance(response.json, dict)
        schedules = [s for host_schedules in response.json.values() for s in host_schedules]
        assert schedules
        for schedule in schedules:
            # Timestamps must be RFC 1123 GMT per the API contract (issue #709),
            # and must represent the exact UTC instant of the stored value.
            parse_http_date(schedule["start"])
            parse_http_date(schedule["end"])
            assert schedule["start"].endswith("GMT")
            assert schedule["end"].endswith("GMT")
        cloud02_schedule = next(s for s in schedules if s["cloud"] == "cloud02")
        expected_start = ensure_utc(parse_datetime(f"{start_str} 22:00"))
        expected_end = ensure_utc(parse_datetime(f"{end_str} 22:00"))
        assert parse_http_date(cloud02_schedule["start"]) == expected_start
        assert parse_http_date(cloud02_schedule["end"]) == expected_end


class TestUpdateSchedule:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_schedule_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a non-existent schedule
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        response = unwrap_json(
            test_client.patch(
                "/api/v3/schedules/999",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Schedule not found: 999"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with a non-existent cloud
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        schedule_update_request["cloud"] = "invalid_cloud"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Cloud not found: {schedule_update_request['cloud']}"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_hostname_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with a non-existent hostname
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        schedule_update_request["hostname"] = "invalid_hostname"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {schedule_update_request['hostname']}"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_date_format(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with an invalid date format
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        schedule_update_request["start"] = "invalid_date"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with an invalid date range
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        schedule_update_request["start"] = "2020-01-01T00:00"
        schedule_update_request["end"] = "2019-01-01T00:00"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_zero_length_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with start equal to end
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={"start": "2020-01-01T00:00", "end": "2020-01-01T00:00"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_start_at_or_after_persisted_end(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update only start to a value at or after the persisted end
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={"start": f"{end_str}T22:00"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_end_at_or_before_persisted_start(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update only end to a value at or before the persisted start
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={"end": f"{start_str}T22:00"},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date range for start or end, start must be before end"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_build_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with an invalid build date range
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        schedule_update_request["build_start"] = "2020-01-01T00:00"
        schedule_update_request["build_end"] = "2019-01-01T00:00"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert (
            response.json["message"]
            == "Invalid date range for build_start or build_end, build_start must be before build_end"
        )

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_missing_all_arguments(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule without any arguments
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert (
            response.json["message"] == "Missing argument: start, end, build_start or build_end (specify at least one)"
        )

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with valid data
        | THEN: User should be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        schedule_update_request = SCHEDULE_1_UPDATE_REQUEST.copy()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json=schedule_update_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["id"] == SCHEDULE_1_RESPONSE["id"]


class TestDeleteSchedule:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_invalid_schedule_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to delete a non-existent schedule
        | THEN: User should not be able to delete the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                "/api/v3/schedules/999",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Schedule not found: 999"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to delete a schedule by ID
        | THEN: User should be able to delete the schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["message"] == "Schedule deleted"


class TestScheduleDaoRangeGuard:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_dao_create_rejects_zero_length(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: The DAO create path is called directly with start == end
        | THEN: It raises instead of persisting a zero-length schedule
        """
        host = HostDao.get_host("host1.example.com")
        assignment = AssignmentDao.get_assignment(1)
        with pytest.raises(InvalidArgument):
            ScheduleDao.create_schedule(
                start=datetime(2099, 1, 1, 10, 0),
                end=datetime(2099, 1, 1, 10, 0),
                assignment=assignment,
                host=host,
            )

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_dao_update_rejects_zero_length(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: The DAO update path is called directly with end at the persisted start
        | THEN: It raises instead of persisting a zero-length schedule
        """
        host = HostDao.get_host("host1.example.com")
        assignment = AssignmentDao.get_assignment(1)
        schedule = ScheduleDao.create_schedule(
            start=datetime(2099, 1, 1, 10, 0),
            end=datetime(2099, 1, 1, 11, 0),
            assignment=assignment,
            host=host,
        )
        try:
            with pytest.raises(InvalidArgument):
                ScheduleDao.update_schedule(schedule.id, end=schedule.start)
            db.session.rollback()
        finally:
            if ScheduleDao.get_schedule(schedule.id):
                ScheduleDao.remove_schedule(schedule.id)


class TestAvailabilitySummaryBoundary:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_scheduled_at_half_open_end(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User asks for the availability summary at the exact moment a schedule ends
        | THEN: The host counts as scheduled before the end and not at the end
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json={
                    "cloud": "cloud02",
                    "hostname": "host1.example.com",
                    "start": "2099-05-01 00:00",
                    "end": "2099-05-01 10:00",
                },
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        params = {
            "two_week_start": "2099-04-15T00:00",
            "two_week_end": "2099-05-15T00:00",
            "four_week_end": "2099-06-01T00:00",
        }
        for now, expected in [("2099-05-01T09:00", 1), ("2099-05-01T10:00", 0)]:
            response = unwrap_json(
                test_client.get(
                    f"/api/v3/hosts/availability_summary?{urlencode({**params, 'now': now})}",
                    headers=auth_header,
                )
            )
            assert response.status_code == 200
            row = next(r for r in response.json if r["model"] == "FC640")
            assert row["scheduled"] == expected


class TestCreateSchedulesBatch:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules without cloud
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "hostnames": ["host2.example.com"],
            "start": "2026-05-08 10:00",
            "end": "2026-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Missing argument: cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_hostnames(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules without hostnames
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "start": "2026-05-08 10:00",
            "end": "2026-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Missing or invalid argument: hostnames (must be a list)"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules for non-existent cloud
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "invalid_cloud",
            "hostnames": ["host2.example.com"],
            "start": "2026-05-08 10:00",
            "end": "2026-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Cloud not found: invalid_cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_format(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with invalid date format
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host2.example.com"],
            "start": "invalid_date",
            "end": "2026-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Invalid date format for start or end, correct format: 'YYYY-MM-DD HH:MM'"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with invalid date range
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host2.example.com"],
            "start": "2026-05-09 22:00",
            "end": "2026-05-08 10:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Invalid date range: start must be before end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_unavailable(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with unavailable host
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()

        conflicting_schedule = {
            "cloud": "cloud02",
            "hostname": "host1.example.com",
            "start": "2026-05-08 09:00",
            "end": "2026-05-10 22:00",
        }
        test_client.post(
            "/api/v3/schedules",
            json=conflicting_schedule,
            headers=auth_header,
        )

        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
            "start": "2026-05-08 10:00",
            "end": "2026-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["message"] == "Some hosts are unavailable"
        assert "host1.example.com" in str(response.json["unavailable_hosts"])

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_use_existing_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules using existing assignment
        | THEN: Schedules should be created successfully
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host4.example.com", "host5.example.com"],
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["schedules_created"] == 2
        assert len(response.json["hostnames"]) == 2
        assert "host4.example.com" in response.json["hostnames"]
        assert "host5.example.com" in response.json["hostnames"]

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts"], indirect=True)
    def test_valid_create_new_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts (no assignments)
        | WHEN: User batch creates schedules with assignment parameters
        | THEN: Assignment and schedules should be created
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud05",
            "hostnames": ["host1.example.com", "host5.example.com"],
            "start": "2027-05-08 10:00",
            "end": "2027-05-09 22:00",
            "description": "Test assignment",
            "owner": "testuser",
            "ticket": "12345",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["schedules_created"] == 2
        assert "assignment_id" in response.json

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts, assignments"], indirect=True)
    def test_valid_now_keyword(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules with 'now' as start
        | THEN: Schedules should be created with current datetime
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud03",
            "hostnames": ["host4.example.com"],
            "start": "now",
            "end": (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M"),
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["schedules_created"] == 1

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts, assignments"], indirect=True)
    @patch("quads.server.blueprints.schedules._trigger_jira_notification")
    def test_valid_jira_integration(self, mock_jira, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules
        | THEN: JIRA notification should be triggered
        """
        mock_jira.return_value = True
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud03",
            "hostnames": ["host5.example.com"],
            "start": "2050-05-08 10:00",
            "end": "2050-05-09 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        assert response.json["jira_updated"] is True
        mock_jira.assert_called_once()


class TestTriggerJiraNotification:
    """Unit tests for _trigger_jira_notification() internal logic."""

    @pytest.fixture(autouse=True)
    def _app_context(self):
        from flask import Flask

        app = Flask(__name__)
        app.extensions["plugin_dispatchers"] = {}
        with app.app_context():
            yield app

    def _make_assignment(self, cloud_name="cloud02", vlan="601", ticket="123"):
        assignment = MagicMock()
        assignment.cloud.name = cloud_name
        assignment.vlan = vlan
        assignment.ticket = ticket
        return assignment

    def _make_dispatcher(self, post_comment_rv=True, transitions=None, post_transition_rv=True):
        dispatcher = MagicMock()
        dispatcher.post_comment = AsyncMock(return_value=post_comment_rv)
        dispatcher.get_transitions = AsyncMock(return_value=transitions or [])
        dispatcher.post_transition = AsyncMock(return_value=post_transition_rv)
        return dispatcher

    def _config_side_effect(self, overrides=None):
        defaults = {
            "jira_docs_links": "http://docs1,http://docs2",
            "jira_vlans_docs_links": "http://vlans1",
        }
        if overrides:
            defaults.update(overrides)

        def side_effect(key, default=None):
            return defaults.get(key, default)

        return side_effect

    def test_no_dispatcher_returns_false(self, _app_context):
        _app_context.extensions["plugin_dispatchers"] = {}
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("builtins.open", side_effect=IOError("No such file"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_template_load_failure_returns_false(self, mock_config, mock_file, _app_context):
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": self._make_dispatcher()}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_post_comment_failure_returns_false(self, mock_config, _app_context):
        dispatcher = self._make_dispatcher(post_comment_rv=False)
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": dispatcher}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_success_with_scheduled_transition(self, mock_config, _app_context):
        dispatcher = self._make_dispatcher(
            transitions=[{"name": "Scheduled", "id": "42"}],
        )
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": dispatcher}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is True
        dispatcher.post_transition.assert_called_once_with("123", "42")

    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_success_no_scheduled_transition(self, mock_config, _app_context):
        dispatcher = self._make_dispatcher(
            transitions=[{"name": "In Progress", "id": "10"}],
        )
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": dispatcher}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is True
        dispatcher.post_transition.assert_not_called()

    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_runtime_exception_returns_false(self, mock_config, _app_context):
        dispatcher = self._make_dispatcher()
        dispatcher.post_comment = AsyncMock(side_effect=Exception("connection refused"))
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": dispatcher}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_dispatcher_methods_called_correctly(self, mock_config, _app_context):
        dispatcher = self._make_dispatcher(
            transitions=[{"name": "Scheduled", "id": "99"}],
        )
        _app_context.extensions["plugin_dispatchers"] = {"ticketing": dispatcher}
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        dispatcher.post_comment.assert_called_once()
        assert dispatcher.post_comment.call_args[0][0] == "123"
        dispatcher.get_transitions.assert_called_once_with("123")
        dispatcher.post_transition.assert_called_once_with("123", "99")


class TestSchedulesInvalidInput:
    def test_non_numeric_schedule_id(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests a schedule with a non-numeric ID
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/schedules/abc"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid schedule id: abc"

    def test_invalid_current_date(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests current schedules with a malformed date
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/schedules/current?date=bogus"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    def test_invalid_hosts_range_start(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests the hosts range with a malformed start date
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/schedules/hosts_range?start=foo"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    def test_invalid_utilization_date(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests utilization stats with an end date in an invalid format
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/schedules/stats/utilization?start=2026-01-01T00:00&end=foo"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    def test_invalid_filter_value_no_sql_leak(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User filters schedules by a non-numeric assignment_id
        | THEN: API returns 400 JSON without leaking raw SQL errors
        """
        response = unwrap_json(test_client.get("/api/v3/schedules?assignment_id=abc"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert "Invalid value for assignment_id" in response.json["message"]
        assert "psycopg2" not in response.json["message"]


class TestScheduleWriteRoutesInvalidInput:
    def test_patch_non_numeric_id(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database and user logged in
        | WHEN: User patches a schedule with a non-numeric ID
        | THEN: API returns 400 JSON instead of a 500
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(test_client.patch("/api/v3/schedules/abc", json={}, headers=auth_header))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts"], indirect=True)
    def test_batch_non_numeric_vlan(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans and hosts
        | WHEN: User batch creates schedules with a non-numeric vlan
        | THEN: API returns 400 JSON instead of a 500
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud04",
            "hostnames": ["host4.example.com"],
            "start": "2027-05-08 10:00",
            "end": "2027-05-09 22:00",
            "description": "vlan test",
            "owner": "tester",
            "ticket": "673997",
            "vlan": "abc",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"


class TestScheduleCreationRace:
    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_batch_rechecks_availability_under_lock(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: A host becomes unavailable between the initial check and the locked re-check
        | THEN: Batch creation fails atomically and no schedules are created
        """
        auth_header = auth.get_auth_header()
        before = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host4.example.com", "host5.example.com"],
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        with patch(
            "quads.server.dao.schedule.ScheduleDao.is_host_available",
            side_effect=[True, True, False, False],
        ):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules/batch",
                    json=batch_request,
                    headers=auth_header,
                )
            )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert any("host4.example.com: Not available" in entry for entry in response.json["unavailable_hosts"])
        after = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        assert len(after) == len(before)

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_single_rechecks_availability_under_lock(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: A host becomes unavailable between the initial check and the locked re-check
        | THEN: Schedule creation fails and no schedule is created
        """
        auth_header = auth.get_auth_header()
        before = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        schedule_request = {
            "cloud": "cloud02",
            "hostname": "host4.example.com",
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        with patch(
            "quads.server.dao.schedule.ScheduleDao.is_host_available",
            side_effect=[False],
        ):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules",
                    json=schedule_request,
                    headers=auth_header,
                )
            )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Host is not available for the specified date range"
        after = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        assert len(after) == len(before)

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts"], indirect=True)
    def test_batch_atomic_on_creation_failure(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans and hosts (no assignments)
        | WHEN: Schedule creation fails after the assignment was created
        | THEN: The whole batch is rolled back and no schedules or assignment remain
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud04",
            "hostnames": ["host4.example.com"],
            "start": "2027-05-08 10:00",
            "end": "2027-05-09 22:00",
            "description": "race test",
            "owner": "tester",
            "ticket": "673999",
        }
        with patch(
            "quads.server.dao.schedule.ScheduleDao.create_schedules",
            side_effect=SQLError("simulated failure"),
        ):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules/batch",
                    json=batch_request,
                    headers=auth_header,
                )
            )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assignments = unwrap_json(test_client.get("/api/v3/assignments", headers=auth_header)).json
        assert all(assignment["ticket"] != "673999" for assignment in assignments)
        schedules = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        assert all(schedule["assignment"]["ticket"] != "673999" for schedule in schedules)

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_batch_existing_assignment_terminated_before_lock(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: The active assignment disappears after the initial check but before the lock
        | THEN: Batch creation is rejected inside the transaction
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host4.example.com"],
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        with patch("quads.server.dao.schedule.ScheduleDao.is_host_available", return_value=True):
            with patch(
                "quads.server.dao.assignment.AssignmentDao.get_active_cloud_assignment",
                side_effect=[SimpleNamespace(), None],
            ):
                response = unwrap_json(
                    test_client.post(
                        "/api/v3/schedules/batch",
                        json=batch_request,
                        headers=auth_header,
                    )
                )
        assert response.status_code == 400
        assert response.json["message"] == "No active assignment for cloud: cloud02"

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts"], indirect=True)
    def test_batch_new_assignment_created_concurrently(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans and hosts
        | WHEN: Another actor creates the active assignment before the lock is taken
        | THEN: Batch creation is rejected inside the transaction
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud04",
            "hostnames": ["host4.example.com"],
            "start": "2027-05-08 10:00",
            "end": "2027-05-09 22:00",
            "description": "race test",
            "owner": "tester",
            "ticket": "673998",
        }
        with patch("quads.server.dao.schedule.ScheduleDao.is_host_available", return_value=True):
            with patch(
                "quads.server.dao.assignment.AssignmentDao.get_active_cloud_assignment",
                side_effect=[None, SimpleNamespace(id=99, owner="rival")],
            ):
                response = unwrap_json(
                    test_client.post(
                        "/api/v3/schedules/batch",
                        json=batch_request,
                        headers=auth_header,
                    )
                )
        assert response.status_code == 400
        assert "already an active assignment" in response.json["message"]

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_single_assignment_terminated_before_lock(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: The active assignment disappears after the initial check but before the lock
        | THEN: Schedule creation is rejected inside the transaction
        """
        auth_header = auth.get_auth_header()
        schedule_request = {
            "cloud": "cloud02",
            "hostname": "host4.example.com",
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        with patch("quads.server.dao.schedule.ScheduleDao.is_host_available", return_value=True):
            with patch(
                "quads.server.dao.assignment.AssignmentDao.get_active_cloud_assignment",
                side_effect=[None],
            ):
                response = unwrap_json(
                    test_client.post(
                        "/api/v3/schedules",
                        json=schedule_request,
                        headers=auth_header,
                    )
                )
        assert response.status_code == 400
        assert response.json["message"] == "No active assignment for cloud: cloud02"

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_single_creation_failure_rolls_back(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: Schedule creation raises an error inside the locked transaction
        | THEN: A 400 is returned and nothing is persisted
        """
        auth_header = auth.get_auth_header()
        before = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        schedule_request = {
            "cloud": "cloud02",
            "hostname": "host4.example.com",
            "start": "2040-05-08 10:00",
            "end": "2040-05-09 22:00",
        }
        with patch("quads.server.dao.schedule.ScheduleDao.is_host_available", return_value=True):
            with patch(
                "quads.server.dao.schedule.ScheduleDao.create_schedule",
                side_effect=SQLError("simulated failure"),
            ):
                response = unwrap_json(
                    test_client.post(
                        "/api/v3/schedules",
                        json=schedule_request,
                        headers=auth_header,
                    )
                )
        assert response.status_code == 400
        assert response.json["message"] == "simulated failure"
        after = unwrap_json(test_client.get("/api/v3/schedules", headers=auth_header)).json
        assert len(after) == len(before)
