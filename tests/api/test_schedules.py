from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock, mock_open
from urllib.parse import urlencode

import pytest

from quads.config import Config
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
)
from tests.helpers import unwrap_json
from quads.server.blueprints.schedules import _trigger_jira_notification
from quads.tools.external.jira import JiraException

prefill_settings = ["clouds, vlans, hosts, assignments"]
prefill_schedule = ["clouds, vlans, hosts, assignments, schedules"]
prefill_self_schedule = ["clouds, vlans, hosts, self_assignments"]
prefill_self_non_schedule = ["clouds, vlans, non_self_hosts, self_assignments"]


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
    def test_invalid_missing_dates(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule without specifying a start or end date
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
            assert response.status_code == 200
            assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self(self, mock_datetime, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule with valid data
        | THEN: User should be able to create a self schedule
        """
        mock_now = datetime(2023, 6, 1, 22, 0)  # 2023-06-01 22:00
        mock_datetime.now.return_value = mock_now

        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=SELF_SCHEDULE_1_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 200

        response_dict = response.json.copy()
        del response_dict["created_at"]
        del response_dict["host"]["created_at"]
        del response_dict["host"]["cloud"]["last_redefined"]
        del response_dict["host"]["default_cloud"]["last_redefined"]
        del response_dict["assignment"]["created_at"]
        del response_dict["assignment"]["cloud"]["last_redefined"]
        SELF_SCHEDULE_1_RESPONSE["end"] = "Sun, 04 Jun 2023 21:00:00 GMT"
        assert response_dict == SELF_SCHEDULE_1_RESPONSE

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_valid_self_limit(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule with valid data but
                exceeding the limit of self scheduling hosts per cloud
        | THEN: User should be able to create a self schedule
        """
        Config.__setattr__("ssm_host_limit", 1)

        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=SELF_SCHEDULE_2_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 200

        response_2 = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=SELF_SCHEDULE_3_REQUEST,
                headers=auth_header,
            )
        )
        assert response_2.status_code == 400
        assert response_2.json["error"] == "Bad Request"
        assert response_2.json["message"] == "Cloud cloud04 has reached the maximum number of hosts"
        Config.__setattr__("ssm_host_limit", 10)

    @pytest.mark.parametrize("prefill", prefill_self_non_schedule, indirect=True)
    def test_self_host_non_self(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule with hosts that are not allowed to self schedule
        | THEN: User should be able to create a self schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=SELF_SCHEDULE_NON_REQUEST,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Host host11.example.com is not allowed to self-schedule"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_overlapping_schedule(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and an existing schedule
        | WHEN: User tries to create a schedule that overlaps with an existing one
        | THEN: User should not be able to create the schedule
        """
        auth_header = auth.get_auth_header()
        existing_schedule = SCHEDULE_1_REQUEST.copy()
        test_client.post("/api/v3/schedules", json=existing_schedule, headers=auth_header)

        overlapping_schedule = SCHEDULE_1_REQUEST.copy()
        now = datetime.now()
        then = now + timedelta(30)
        overlapping_schedule["start"] = now.strftime("%Y-%m-%d %H:%M")
        overlapping_schedule["end"] = then.strftime("%Y-%m-%d %H:%M")

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=overlapping_schedule,
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Host is not available for the specified date range"


class TestReadSchedule:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_all(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to read all schedules
        | THEN: User should be able to read all schedules
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules",
                headers=auth_header,
            )
        )
        response.json.sort(key=lambda x: x["id"])
        schedule_responses = [
            SCHEDULE_1_RESPONSE.copy(),
            SCHEDULE_2_RESPONSE.copy(),
            SELF_SCHEDULE_1_RESPONSE.copy(),
            SELF_SCHEDULE_2_RESPONSE.copy(),
        ]
        for i, resp in enumerate(schedule_responses):
            resp["assignment"]["cloud"]["last_redefined"] = response.json[i]["assignment"]["cloud"]["last_redefined"]
            resp["assignment"]["created_at"] = response.json[i]["assignment"]["created_at"]
            resp["created_at"] = response.json[i]["created_at"]
            resp["host"]["created_at"] = response.json[i]["host"]["created_at"]
            resp["host"]["cloud"]["last_redefined"] = response.json[i]["host"]["cloud"]["last_redefined"]
            resp["host"]["default_cloud"]["last_redefined"] = response.json[i]["host"]["default_cloud"][
                "last_redefined"
            ]
            resp["start"] = response.json[i]["start"]
            resp["end"] = response.json[i]["end"]
        assert response.status_code == 200
        assert response.json == schedule_responses

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_single_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to read a schedule by ID that does not exist
        | THEN: User should not be able to read the schedule
        """
        auth_header = auth.get_auth_header()
        invalid_schedule_id = 42
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/{invalid_schedule_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Schedule not found: {invalid_schedule_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_single(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to read a schedule by ID that exists
        | THEN: User should be able to read the schedule
        """
        auth_header = auth.get_auth_header()
        resp = SCHEDULE_2_RESPONSE.copy()
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules/{resp['id']}",
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
        assert response.status_code == 200
        assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_current(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to read the current schedule (by hostname, by date and by cloud and date)
        | THEN: User should be able to read the current schedule(s) for each case
        """
        auth_header = auth.get_auth_header()
        schedule_responses = [
            [SCHEDULE_1_RESPONSE.copy()],
            [SCHEDULE_2_RESPONSE.copy()],
            [SCHEDULE_1_RESPONSE.copy()],
            [],
        ]
        future_date = datetime.now() + timedelta(days=365)
        future_str = future_date.strftime("%Y-%m-%d")
        requests = [
            {"host": schedule_responses[0][0]["host"]["name"]},
            {"date": "2043-01-01T22:00"},
            {"cloud": "cloud02", "date": f"{future_str}T22:00"},
            {
                "cloud": "cloud04",
                "host": schedule_responses[0][0]["host"]["name"],
                "date": "2050-01-01T22:00",
            },
        ]
        for i, resp, req in zip(range(len(schedule_responses)), schedule_responses, requests):
            response = unwrap_json(
                test_client.get(
                    f"/api/v3/schedules/current/?{urlencode(req)}",
                    headers=auth_header,
                )
            )
            if not resp:
                assert response.status_code == 200
                assert response.json == resp
                continue
            resp[0]["assignment"]["cloud"]["last_redefined"] = response.json[0]["assignment"]["cloud"][
                "last_redefined"
            ]
            resp[0]["assignment"]["created_at"] = response.json[0]["assignment"]["created_at"]
            resp[0]["created_at"] = response.json[0]["created_at"]
            resp[0]["host"]["created_at"] = response.json[0]["host"]["created_at"]
            resp[0]["host"]["cloud"]["last_redefined"] = response.json[0]["host"]["cloud"]["last_redefined"]
            resp[0]["host"]["default_cloud"]["last_redefined"] = response.json[0]["host"]["default_cloud"][
                "last_redefined"
            ]
            resp[0]["start"] = response.json[0]["start"]
            resp[0]["end"] = response.json[0]["end"]
            assert response.status_code == 200
            assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_filter(self, test_client, auth, prefill):
        """
        | GIVEN: : Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to filter schedules by an invalid field
        | THEN: User should not be able to get any schedule
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules?start=invalid",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date format for start: invalid"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_filter(self, test_client, auth, prefill):
        """
        | GIVEN: : Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to filter schedules by with a valid filter
        | THEN: User should be able to read the appropriate schedule(s)
        """
        auth_header = auth.get_auth_header()
        hostname = SCHEDULE_1_RESPONSE["host"]["name"]
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?host.name={hostname}",
                headers=auth_header,
            )
        )

        response.json.sort(key=lambda x: x["id"])
        schedule_responses = [SCHEDULE_1_RESPONSE.copy(), SELF_SCHEDULE_1_RESPONSE.copy()]
        for i, resp in enumerate(schedule_responses):
            resp["assignment"]["cloud"]["last_redefined"] = response.json[i]["assignment"]["cloud"]["last_redefined"]
            resp["assignment"]["created_at"] = response.json[i]["assignment"]["created_at"]
            resp["created_at"] = response.json[i]["created_at"]
            resp["host"]["created_at"] = response.json[i]["host"]["created_at"]
            resp["host"]["cloud"]["last_redefined"] = response.json[i]["host"]["cloud"]["last_redefined"]
            resp["host"]["default_cloud"]["last_redefined"] = response.json[i]["host"]["default_cloud"][
                "last_redefined"
            ]
            resp["start"] = response.json[i]["start"]
            resp["end"] = response.json[i]["end"]
        assert response.status_code == 200
        assert response.json == schedule_responses

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_future(self, test_client, auth, prefill):
        """
        | GIVEN: : Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to read future schedules
        | THEN: User should be able to read the appropriate schedule(s)
        """
        auth_header = auth.get_auth_header()
        schedule_responses = [
            SCHEDULE_2_RESPONSE.copy(),
        ]
        response = unwrap_json(
            test_client.get(
                "/api/v3/schedules/future?host=host3.example.com",
                headers=auth_header,
            )
        )
        for resp, sched_resp in zip(response.json, schedule_responses):
            sched_resp["created_at"] = resp["created_at"]
            sched_resp["start"] = resp["start"]
            sched_resp["end"] = resp["end"]
        assert response.status_code == 200
        assert response.json == schedule_responses


class TestUpdateSchedule:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_single_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule by ID that does not exist
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        invalid_schedule_id = 42
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{invalid_schedule_id}",
                json={},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Schedule not found: {invalid_schedule_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_no_args(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule by ID with no data
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
            response.json["message"] == "Missing argument: start, end, build_start or build_end (specify at least "
            "one)"
        )

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_key_value_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule by ID with invalid data
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        invalid_hostname = "invalid_hostname"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={"hostname": invalid_hostname},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Host not found: {invalid_hostname}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_format(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule and passes a date in an invalid format
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        date_type = "start"
        invalid_date = "invalid_date"
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                json={f"{date_type}": invalid_date},
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid date format for start or end, correct format: 'YYYY-MM-DDTHH:MM'"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_ranges(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule and passes a date that is out of range (tests all possible date ranges)
        | THEN: User should not be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        reqs = [
            {"start": "2020-01-01T00:00", "end": "2019-01-01T00:00"},
            {"build_start": "2040-01-01T00:00", "build_end": "2039-01-01T00:00"},
            {"start": "2020-01-01T00:00", "build_start": "2019-01-01T00:00"},
            {"end": "2037-01-01T00:00", "build_end": "2038-01-01T00:00"},
        ]
        resp_messages = [
            "Invalid date range for start or end, start must be before end",
            "Invalid date range for build_start or build_end, build_start must be before build_end",
            "Invalid date range for start or build_start, start must be before build_start",
            "Invalid date range for end or build_end, build_end must be before end",
        ]
        for req, resp_message in zip(reqs, resp_messages):
            response = unwrap_json(
                test_client.patch(
                    f"/api/v3/schedules/{SCHEDULE_1_RESPONSE['id']}",
                    json=req,
                    headers=auth_header,
                )
            )
            assert response.status_code == 400
            assert response.json["error"] == "Bad Request"
            assert response.json["message"] == resp_message

    @pytest.mark.parametrize("prefill", prefill_schedule, indirect=True)
    def test_valid(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to update a schedule with valid data
        | THEN: User should be able to update the schedule
        """
        auth_header = auth.get_auth_header()
        resp = SCHEDULE_1_RESPONSE.copy()
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/schedules/{resp['id']}",
                json=SCHEDULE_1_UPDATE_REQUEST,
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
        resp["build_start"] = response.json["build_start"]
        resp["build_end"] = response.json["build_end"]
        assert response.status_code == 200
        assert response.json == resp


class TestDeleteSchedule:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules from TestCreateSchedule
        | WHEN: User tries to delete a schedule by ID that does not exist
        | THEN: User should not be able to delete the schedule
        """
        auth_header = auth.get_auth_header()
        invalid_schedule_id = 999
        response = unwrap_json(
            test_client.delete(
                f"/api/v3/schedules/{invalid_schedule_id}",
                headers=auth_header,
            )
        )
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == f"Schedule not found: {invalid_schedule_id}"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
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


class TestCreateSchedulesBatch:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_cloud(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules without specifying a cloud
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Missing argument: cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_hostnames(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules without specifying hostnames
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Missing or invalid argument: hostnames (must be a list)"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_hostnames_not_a_list(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with hostnames as a string instead of a list
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": "host1.example.com",
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Missing or invalid argument: hostnames (must be a list)"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_missing_dates(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules without specifying start or end
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
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
        assert response.json["message"] == "Missing argument: start or end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_cloud_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules for a non-existent cloud
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "invalid_cloud",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Cloud not found: invalid_cloud"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_format(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with an invalid date format
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
            "start": "invalid_date",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Invalid date format for start or end, correct format: 'YYYY-MM-DD HH:MM'"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_date_range(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with start after end
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-02 22:00",
            "end": "2040-06-01 10:00",
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
        assert response.json["message"] == "Invalid date range: start must be before end"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_no_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules on a cloud with no active assignment
        |       and without providing assignment parameters
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud01",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "No active assignment for cloud: cloud01"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_not_found(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with a non-existent host
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["nonexistent.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Some hosts are unavailable"
        assert "nonexistent.example.com: Host not found" in response.json["unavailable_hosts"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_host_unavailable(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and an existing schedule
        | WHEN: User tries to batch create schedules for a host that already has a conflicting schedule
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/schedules",
            json={
                "cloud": "cloud02",
                "hostname": "host1.example.com",
                "start": "2040-06-01 09:00",
                "end": "2040-06-03 22:00",
            },
            headers=auth_header,
        )
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
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
        assert response.json["message"] == "Some hosts are unavailable"
        assert "host1.example.com" in str(response.json["unavailable_hosts"])

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_partial_assignment_params(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with only some assignment parameters
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud05",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
            "description": "Test assignment",
            "owner": "testuser",
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
        assert response.json["message"] == "When creating assignment, description, owner, and ticket are all required"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_invalid_assignment_already_exists(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to batch create schedules with assignment parameters
        |       on a cloud that already has an active assignment
        | THEN: User should not be able to create schedules
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com"],
            "start": "2040-06-01 10:00",
            "end": "2040-06-02 22:00",
            "description": "Conflict assignment",
            "owner": "testuser",
            "ticket": "99999",
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
        assert "There is already an active assignment for cloud02" in response.json["message"]

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_existing_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules using an existing assignment on cloud02
        | THEN: Schedules should be created successfully for all specified hosts
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host1.example.com", "host4.example.com"],
            "start": "2041-06-01 10:00",
            "end": "2041-06-02 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["schedules_created"] == 2
        assert len(response.json["hostnames"]) == 2
        assert "host1.example.com" in response.json["hostnames"]
        assert "host4.example.com" in response.json["hostnames"]
        assert "assignment_id" in response.json

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_single_host(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates a schedule for a single host
        | THEN: Schedule should be created successfully
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud03",
            "hostnames": ["host5.example.com"],
            "start": "2042-06-01 10:00",
            "end": "2042-06-02 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["schedules_created"] == 1
        assert response.json["hostnames"] == ["host5.example.com"]

    @pytest.mark.parametrize("prefill", ["clouds, vlans, hosts"], indirect=True)
    def test_valid_create_new_assignment(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans and hosts (no assignments)
        | WHEN: User batch creates schedules with assignment parameters on a cloud
        |       that has no existing assignment
        | THEN: A new assignment and schedules should be created
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud05",
            "hostnames": ["host1.example.com", "host5.example.com"],
            "start": "2043-06-01 10:00",
            "end": "2043-06-02 22:00",
            "description": "Batch test assignment",
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
        assert response.status_code == 200
        assert response.json["schedules_created"] == 2
        assert "assignment_id" in response.json
        assert response.json["assignment_id"] is not None

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_now_keyword(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules with 'now' as the start date
        | THEN: Schedules should be created with the current datetime as start
        """
        auth_header = auth.get_auth_header()
        end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")
        batch_request = {
            "cloud": "cloud03",
            "hostnames": ["host1.example.com"],
            "start": "now",
            "end": end_date,
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["schedules_created"] == 1

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    @patch("quads.server.blueprints.schedules._trigger_jira_notification")
    def test_valid_jira_integration(self, mock_jira, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules and JIRA notification is configured
        | THEN: JIRA notification should be triggered and response should indicate success
        """
        mock_jira.return_value = True
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host5.example.com"],
            "start": "2044-06-01 10:00",
            "end": "2044-06-02 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["jira_updated"] is True
        mock_jira.assert_called_once()

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_jira_no_dispatcher(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules without JIRA dispatcher configured
        | THEN: Schedules should be created but jira_updated should be False
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud03",
            "hostnames": ["host2.example.com"],
            "start": "2045-06-01 10:00",
            "end": "2045-06-02 22:00",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json=batch_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["schedules_created"] == 1
        assert response.json["jira_updated"] is False


class TestTriggerJiraNotification:
    """Unit tests for _trigger_jira_notification() internal logic."""

    def _make_assignment(self, cloud_name="cloud02", vlan="601", ticket="123"):
        assignment = MagicMock()
        assignment.cloud.name = cloud_name
        assignment.vlan = vlan
        assignment.ticket = ticket
        return assignment

    def _config_side_effect(self, overrides=None):
        defaults = {
            "jira_url": "https://jira.example.com",
            "jira_username": "testuser",
            "jira_password": "testpass",
            "jira_docs_links": "http://docs1,http://docs2",
            "jira_vlans_docs_links": "http://vlans1",
        }
        if overrides:
            defaults.update(overrides)

        def side_effect(key, default=None):
            return defaults.get(key, default)

        return side_effect

    @patch("quads.server.blueprints.schedules.Config")
    def test_no_jira_url_returns_false(self, mock_config):
        mock_config.get = MagicMock(side_effect=self._config_side_effect({"jira_url": None}))
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("builtins.open", side_effect=IOError("No such file"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_template_load_failure_returns_false(self, mock_config, mock_file):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("quads.server.blueprints.schedules.Jira", side_effect=JiraException("auth failed"))
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_jira_init_exception_returns_false(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("quads.server.blueprints.schedules.Jira")
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_post_comment_failure_returns_false(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        mock_jira = MagicMock()
        mock_jira.post_comment = AsyncMock(return_value=False)
        mock_jira_cls.return_value = mock_jira
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("quads.server.blueprints.schedules.Jira")
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_success_with_scheduled_transition(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        mock_jira = MagicMock()
        mock_jira.post_comment = AsyncMock(return_value=True)
        mock_jira.get_transitions = AsyncMock(
            return_value=[{"name": "Scheduled", "id": "42"}]
        )
        mock_jira.post_transition = AsyncMock(return_value=True)
        mock_jira_cls.return_value = mock_jira
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is True
        mock_jira.post_transition.assert_called_once_with("123", "42")

    @patch("quads.server.blueprints.schedules.Jira")
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_success_no_scheduled_transition(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        mock_jira = MagicMock()
        mock_jira.post_comment = AsyncMock(return_value=True)
        mock_jira.get_transitions = AsyncMock(
            return_value=[{"name": "In Progress", "id": "10"}]
        )
        mock_jira_cls.return_value = mock_jira
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is True
        mock_jira.post_transition.assert_not_called()

    @patch("quads.server.blueprints.schedules.Jira")
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_jira_runtime_exception_returns_false(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        mock_jira = MagicMock()
        mock_jira.post_comment = AsyncMock(side_effect=Exception("connection refused"))
        mock_jira_cls.return_value = mock_jira
        assignment = self._make_assignment()

        result = _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        assert result is False

    @patch("quads.server.blueprints.schedules.Jira")
    @patch("builtins.open", mock_open(read_data="{{cloud}} scheduled"))
    @patch("quads.server.blueprints.schedules.Config")
    def test_jira_constructor_receives_correct_params(self, mock_config, mock_jira_cls):
        mock_config.get = MagicMock(side_effect=self._config_side_effect())
        mock_config.TEMPLATES_PATH = "/fake/templates"
        mock_jira = MagicMock()
        mock_jira.post_comment = AsyncMock(return_value=True)
        mock_jira.get_transitions = AsyncMock(return_value=[])
        mock_jira_cls.return_value = mock_jira
        assignment = self._make_assignment()

        _trigger_jira_notification(assignment, ["host1"], "2050-01-01", "2050-01-02")

        call_kwargs = mock_jira_cls.call_args
        assert call_kwargs[0][0] == "https://jira.example.com"
        assert call_kwargs[1]["username"] == "testuser"
        assert call_kwargs[1]["password"] == "testpass"
