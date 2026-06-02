import logging
from datetime import timedelta
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
        "movecommand": "/quads/quads/tools/move_and_rebuild.py",
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


class TestMoveProgress:
    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_create_move_progress(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        data = {
            "hostname": "host2.example.com",
            "source_cloud": "cloud01",
            "target_cloud": "cloud02",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/",
                json=data,
                headers=auth_header,
            )
        )
        assert response.status_code == 201
        result = response.json
        assert result["host"] == "host2.example.com"
        assert result["source_cloud"] == "cloud01"
        assert result["target_cloud"] == "cloud02"
        assert result["status"] == "pending"
        assert result["id"] is not None

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_all_active_progress(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/",
            json={
                "hostname": "host2.example.com",
                "source_cloud": "cloud01",
                "target_cloud": "cloud02",
            },
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
    def test_get_move_progress_by_host(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/",
            json={
                "hostname": "host3.example.com",
                "source_cloud": "cloud01",
                "target_cloud": "cloud03",
            },
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

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_update_move_progress(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        create_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/",
                json={
                    "hostname": "host2.example.com",
                    "source_cloud": "cloud01",
                    "target_cloud": "cloud02",
                },
                headers=auth_header,
            )
        )
        progress_id = create_resp.json["id"]
        response = unwrap_json(
            test_client.patch(
                f"/api/v3/moves/progress/{progress_id}",
                json={"status": "ipmi_config", "message": "IPMI configured"},
                headers=auth_header,
            )
        )
        assert response.status_code == 200
        assert response.json["status"] == "ipmi_config"
        assert response.json["message"] == "IPMI configured"

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_create_move_progress_no_auth(self, test_client, auth, prefill):
        data = {
            "hostname": "host2.example.com",
            "source_cloud": "cloud01",
            "target_cloud": "cloud02",
        }
        response = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/",
                json=data,
            )
        )
        assert response.status_code in (400, 401)

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_get_move_progress_not_found(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        response = unwrap_json(
            test_client.get(
                "/api/v3/moves/progress/nonexistent.example.com",
                headers=auth_header,
            )
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_move_progress_lifecycle(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        create_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/",
                json={
                    "hostname": "host2.example.com",
                    "source_cloud": "cloud01",
                    "target_cloud": "cloud02",
                },
                headers=auth_header,
            )
        )
        progress_id = create_resp.json["id"]

        stages = ["switch_config", "ipmi_config", "hardware_prep", "power_on", "provisioning", "completed"]
        for stage in stages:
            resp = unwrap_json(
                test_client.patch(
                    f"/api/v3/moves/progress/{progress_id}",
                    json={"status": stage},
                    headers=auth_header,
                )
            )
            assert resp.status_code == 200
            assert resp.json["status"] == stage

        assert resp.json["completed_at"] is not None

    @pytest.mark.parametrize("prefill", prefill_settings, indirect=True)
    def test_create_move_progress_batch(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        data = {
            "records": [
                {
                    "hostname": "host2.example.com",
                    "source_cloud": "cloud01",
                    "target_cloud": "cloud02",
                },
                {
                    "hostname": "host3.example.com",
                    "source_cloud": "cloud01",
                    "target_cloud": "cloud03",
                },
            ]
        }
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
    def test_get_progress_cloud_filter(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        test_client.post(
            "/api/v3/moves/progress/",
            json={
                "hostname": "host2.example.com",
                "source_cloud": "cloud01",
                "target_cloud": "cloud02",
            },
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
    def test_move_progress_failure(self, test_client, auth, prefill):
        auth_header = auth.get_auth_header()
        create_resp = unwrap_json(
            test_client.post(
                "/api/v3/moves/progress/",
                json={
                    "hostname": "host2.example.com",
                    "source_cloud": "cloud01",
                    "target_cloud": "cloud02",
                },
                headers=auth_header,
            )
        )
        progress_id = create_resp.json["id"]
        resp = unwrap_json(
            test_client.patch(
                f"/api/v3/moves/progress/{progress_id}",
                json={"status": "failed", "error_message": "IPMI timeout"},
                headers=auth_header,
            )
        )
        assert resp.status_code == 200
        assert resp.json["status"] == "failed"
        assert resp.json["error_message"] == "IPMI timeout"
        assert resp.json["completed_at"] is not None
