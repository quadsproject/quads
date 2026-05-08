from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
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
    def test_invalid_host_not_available(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a schedule for a host that is not available
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
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
            assert response.status_code == 200
            assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    @patch("quads.server.blueprints.schedules.datetime")
    def test_valid_self(self, mock_datetime, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule with valid data
        | THEN: User should be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_requests = [
            SELF_SCHEDULE_1_REQUEST.copy(),
            SELF_SCHEDULE_2_REQUEST.copy(),
            SELF_SCHEDULE_3_REQUEST.copy(),
        ]
        schedule_responses = [
            SELF_SCHEDULE_1_RESPONSE.copy(),
            SELF_SCHEDULE_2_RESPONSE.copy(),
            SELF_SCHEDULE_2_RESPONSE.copy(),
        ]
        now = datetime.now()
        mock_datetime.now.return_value = now
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
            assert response.status_code == 200

    @pytest.mark.parametrize("prefill", prefill_self_schedule, indirect=True)
    def test_valid_self_limit(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User tries to create a self schedule that exceeds the limit
        | THEN: User should not be able to create a schedule
        """
        auth_header = auth.get_auth_header()
        schedule_requests = [
            SELF_SCHEDULE_1_REQUEST.copy(),
            SELF_SCHEDULE_2_REQUEST.copy(),
            SELF_SCHEDULE_3_REQUEST.copy(),
        ]
        for i, req in enumerate(schedule_requests):
            response = unwrap_json(
                test_client.post(
                    "/api/v3/schedules",
                    json=req,
                    headers=auth_header,
                )
            )
            if i < 2:
                assert response.status_code == 200
            else:
                assert response.status_code == 400
                assert response.json["error"] == "Bad Request"
                assert (
                    response.json["message"]
                    == f"Cloud {schedule_requests[i]['cloud']} has reached the maximum number of hosts"
                )

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
        schedule_request["start"] = "now"
        schedule_request["end"] = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M")

        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json=schedule_request,
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        start_time = datetime.fromisoformat(response.json["start"].replace("Z", ""))
        now = datetime.now()
        assert abs((start_time - now).total_seconds()) < 60


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
        | WHEN: User tries to filter schedules by cloud
        | THEN: User should be able to get schedules
        """
        auth_header = auth.get_auth_header()
        filters = {"cloud": "cloud02"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/schedules?{urlencode(filters)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
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
            response.json["message"]
            == "Missing argument: start, end, build_start or build_end (specify at least one)"
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
            "hostnames": ["host2.example.com", "host3.example.com"],
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
        assert response.status_code == 200
        assert response.json["schedules_created"] == 2
        assert len(response.json["hostnames"]) == 2
        assert "host2.example.com" in response.json["hostnames"]
        assert "host3.example.com" in response.json["hostnames"]

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
            "hostnames": ["host2.example.com", "host3.example.com"],
            "start": "2026-05-08 10:00",
            "end": "2026-05-09 22:00",
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
        assert response.status_code == 200
        assert response.json["schedules_created"] == 2
        assert "assignment_id" in response.json

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_now_keyword(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts and assignments
        | WHEN: User batch creates schedules with 'now' as start
        | THEN: Schedules should be created with current datetime
        """
        auth_header = auth.get_auth_header()
        batch_request = {
            "cloud": "cloud02",
            "hostnames": ["host2.example.com"],
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
        assert response.status_code == 200
        assert response.json["schedules_created"] == 1

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
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
            "cloud": "cloud02",
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
        assert response.status_code == 200
        assert response.json["jira_updated"] is True
        mock_jira.assert_called_once()
