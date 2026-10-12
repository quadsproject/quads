import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

import pytest

from quads.cli import QuadsCli
from quads.config import DEFAULT_CONF_PATH, Config
from quads.quads_api import QuadsApi
from tests.config import start_date
from tests.helpers import unwrap_json

prefill_settings = ["clouds, vlans, hosts, assignments, schedules"]

_logger = logging.getLogger("test_log")
_logger.setLevel(logging.INFO)
_logger.propagate = True


def quads_cli_call(action):
    _cli_args = {
        "datearg": None,
        "filter": None,
        "force": "False",
        "dryrun": None,
    }
    Config.load_from_yaml(DEFAULT_CONF_PATH)
    quads = QuadsApi(config=Config)
    qcli = QuadsCli(quads=quads, logger=_logger)
    try:
        qcli.run(action=action, cli_args=_cli_args)
    except Exception as ex:
        raise ex


class TestReadMoves:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_not_moved(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules and NOT moved out hosts
        | WHEN: User tries to read a list of all hosts that need to be moved
        | THEN: User should be able to get the list of hosts with information where they need to moved
        """
        auth_header = auth.get_auth_header()
        resp = [
            {"current": "cloud01", "host": "host2.example.com", "new": "cloud02"},
            {"current": "cloud01", "host": "host3.example.com", "new": "cloud03"},
        ]
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_date(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules and moved out hosts
        | WHEN: User tries to read a list of all hosts that need to be moved at a specified date
        | THEN: User should be able to get the list of hosts with information where they need to moved
        """
        auth_header = auth.get_auth_header()
        date = start_date + timedelta(days=2)
        req = {"date": f"{date.strftime('%Y-%m-%d')}T22:00"}
        resp = [
            {"current": "cloud01", "host": "host2.example.com", "new": "cloud02"},
            {"current": "cloud01", "host": "host3.example.com", "new": "cloud03"},
        ]
        response = unwrap_json(
            test_client.get(
                f"/api/v3/moves?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json == resp

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_valid_at_exact_end(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: User asks for moves at the exact moment a schedule ends
        | THEN: The host is no longer scheduled and does not need a move (half-open [start, end))
        """
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.post(
                "/api/v3/schedules",
                json={
                    "cloud": "cloud02",
                    "hostname": "host4.example.com",
                    "start": "2099-04-01 00:00",
                    "end": "2099-04-01 08:00",
                },
                headers=auth_header,
            )
        )
        assert response.status_code == 201

        req = {"date": "2099-04-01T08:00"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/moves?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert "host4.example.com" not in [m["host"] for m in response.json]

        req = {"date": "2099-04-01T07:00"}
        response = unwrap_json(
            test_client.get(
                f"/api/v3/moves?{urlencode(req)}",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        moves = {m["host"]: m for m in response.json}
        assert moves["host4.example.com"]["new"] == "cloud02"


class TestMoveStatus:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_start_move_batch(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        data = {"hostnames": ["host2.example.com", "host3.example.com"]}
        response = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json=data,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        result = response.json
        assert "host2.example.com" in result
        assert "host3.example.com" in result

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_start_move_batch_skips_hosts_without_current_schedule(self, test_client, auth, prefill):
        """Reclaim moves (host with no current schedule) are skipped, not a 500."""
        auth_header = auth.get_auth_header()
        data = {"hostnames": ["host1.example.com", "host2.example.com"]}
        response = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json=data,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        result = response.json
        assert "host2.example.com" in result
        assert "host1.example.com" not in result

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_all_active_status(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/batch",
            json={"hostnames": ["host2.example.com"]},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert isinstance(response.json, list)
        assert len(response.json) >= 1

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_move_status_by_host(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/batch",
            json={"hostnames": ["host3.example.com"]},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/host3.example.com",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["host"] == "host3.example.com"
        assert response.json["status"] == "pending"
        assert response.json["source_cloud"] == "cloud01"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_source_cloud_persisted_at_move_start(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/batch",
            json={"hostnames": ["host3.example.com"]},
            headers=auth_header,
        )
        # Update host's cloud to simulate the release plugin
        test_client.patch(
            "/api/v3/hosts/host3.example.com",
            json={"cloud": "cloud03"},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/host3.example.com",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["source_cloud"] == "cloud01"
        assert response.json["target_cloud"] == "cloud03"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_update_move_status(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host2.example.com"]
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/moves/progress/{schedule_id}",
                json={"status": "ipmi_config", "message": "IPMI configured"},
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "ipmi_config"
        assert response.json["message"] == "IPMI configured"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_start_move_batch_no_auth(self, test_client, auth, prefill):
        response = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
            )
        )
        assert response.status_code in (400, 401)

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_move_status_not_found(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/nonexistent.example.com",
                headers=auth_header,
            )
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_move_status_lifecycle(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host2.example.com"]

        stages = ["switch_config", "ipmi_config", "hardware_prep", "power_on", "provisioning", "completed"]
        for stage in stages:
            resp = unwrap_json(
                test_client.patch(
                    f"/api/v3/moves/progress/{schedule_id}",
                    json={"status": stage},
                    headers=auth_header,
                )
            )
            assert resp.status_code == 200
            assert resp.json["status"] == stage

        assert resp.json["completed_at"] is not None

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_status_cloud_filter(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/batch",
            json={"hostnames": ["host2.example.com"]},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/?cloud=cloud02",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        for move in response.json:
            assert move["target_cloud"] == "cloud02"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_move_status_failure(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host2.example.com"]
        resp = unwrap_json(
            test_client.patch(
                f"/api/v3/moves/progress/{schedule_id}",
                json={"status": "failed", "error_message": "IPMI timeout"},
                headers=auth_header,
            )
        )
        assert resp.status_code == 200
        assert resp.json["status"] == "failed"
        assert resp.json["error_message"] == "IPMI timeout"
        assert resp.json["completed_at"] is not None

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_failed_move_visible_in_active(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host2.example.com"]
        test_client.patch(
            f"/api/v3/moves/progress/{schedule_id}",
            json={"status": "failed", "error_message": "Failed at hardware_prep"},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        failed_hosts = [m for m in response.json if m["status"] == "failed"]
        assert len(failed_hosts) >= 1
        assert failed_hosts[0]["error_message"] == "Failed at hardware_prep"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_failed_move_visible_by_hostname(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host3.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host3.example.com"]
        test_client.patch(
            f"/api/v3/moves/progress/{schedule_id}",
            json={"status": "failed", "error_message": "Failed at power_on"},
            headers=auth_header,
        )
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/host3.example.com",
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "failed"
        assert response.json["error_message"] == "Failed at power_on"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_update_move_status_invalid(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/batch",
                json={"hostnames": ["host2.example.com"]},
                headers=auth_header,
            )
        )
        schedule_id = batch_resp.json["host2.example.com"]
        resp = unwrap_json(
            test_client.patch(
                f"/api/v3/moves/progress/{schedule_id}",
                json={"status": "foobar"},
                headers=auth_header,
            )
        )
        assert resp.status_code == 400


class TestReadMovesInvalidInput:
    def test_invalid_date(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests moves with a malformed date
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/moves/?date=bogus"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"

    def test_invalid_status(self, test_client, auth):
        """
        | GIVEN: Client with defaults in database
        | WHEN: User requests move progress with an invalid status
        | THEN: API returns 400 JSON instead of a 500
        """
        response = unwrap_json(test_client.get("/api/v3/moves/progress/?status=bogus"))
        assert response.status_code == 400
        assert response.json["error"] == "Bad Request"
        assert response.json["message"] == "Invalid status: bogus"


class TestMovesTerminatedAssignment:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_no_moves_from_terminated_assignment_future_schedule(self, test_client, auth, prefill):
        """
        | GIVEN: Defaults, auth, clouds, vlans, hosts, assignments and schedules
        | WHEN: Assignment has a future schedule for an unmoved host, then the
        |       assignment is terminated
        | THEN: The stale future schedule must not drive a move into the
        |       terminated assignment's cloud
        """
        auth_header = auth.get_auth_header()
        future_start = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M")
        future_end = (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%d %H:%M")
        batch_resp = unwrap_json(
            test_client.post(
                "/api/v3/schedules/batch",
                json={
                    "cloud": "cloud02",
                    "hostnames": ["host4.example.com"],
                    "start": future_start,
                    "end": future_end,
                },
                headers=auth_header,
            )
        )
        assert batch_resp.status_code == 201

        query_date = (datetime.now() + timedelta(days=2, minutes=1)).strftime("%Y-%m-%dT%H:%M")
        resp = unwrap_json(test_client.get(f"/api/v3/moves?date={query_date}", headers=auth_header))
        assert any(m["host"] == "host4.example.com" and m["new"] == "cloud02" for m in resp.json)

        term_resp = unwrap_json(test_client.post("/api/v3/assignments/terminate/1/", json={}, headers=auth_header))
        assert term_resp.status_code == 200

        resp = unwrap_json(test_client.get(f"/api/v3/moves?date={query_date}", headers=auth_header))
        assert all(m["host"] != "host4.example.com" for m in resp.json)
