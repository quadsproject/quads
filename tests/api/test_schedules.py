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
            assert response.status_code == 200
            assert response.json == resp

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
        assert response.status_code == 200

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
            assert response.status_code == 200

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
        assert response.status_code == 200
        from email.utils import parsedate_to_datetime

        start_time = parsedate_to_datetime(response.json["start"]).replace(tzinfo=None)
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
        assert response.status_code == 200
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
        assert response.status_code == 200
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
        assert response.status_code == 200
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
        assert response.status_code == 200
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
