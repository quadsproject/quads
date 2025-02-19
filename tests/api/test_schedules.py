from unittest.mock import patch

import pytest

from datetime import datetime, timedelta
from urllib.parse import urlencode

from quads.config import Config

from tests.helpers import unwrap_json
from tests.config import (
    SCHEDULE_1_REQUEST,
    SCHEDULE_1_RESPONSE,
    SCHEDULE_2_REQUEST,
    SCHEDULE_2_RESPONSE,
    SCHEDULE_1_UPDATE_REQUEST,
    SELF_SCHEDULE_1_REQUEST,
    SELF_SCHEDULE_1_RESPONSE,
    SELF_SCHEDULE_2_REQUEST,
    SELF_SCHEDULE_2_RESPONSE,
    SELF_SCHEDULE_NON_REQUEST,
    SELF_SCHEDULE_3_REQUEST,
)

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
            SELF_SCHEDULE_2_RESPONSE.copy(),
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
