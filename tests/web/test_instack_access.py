from types import SimpleNamespace
import os

import pytest

from quads.web.app import create_app
from quads.web.blueprints import instack as instack_module
import quads.web.app as web_app

ASSIGNMENT = SimpleNamespace(owner="alice", ccuser=["bob", "carol@example.com"])
FILE_CONTENT = '{"nodes": [{"name": "host1"}]}'


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("web_content")
    instack_dir = root / "instack"
    instack_dir.mkdir()
    (instack_dir / "cloud02_instackenv.json").write_text(FILE_CONTENT)
    original = web_app.WEB_CONTENT_PATH
    web_app.WEB_CONTENT_PATH = str(root)
    flask_app = create_app()
    yield flask_app, root
    web_app.WEB_CONTENT_PATH = original


def make_quads(token_user=None, assignment=None):
    return SimpleNamespace(
        get_authenticated_user=lambda token: token_user,
        get_active_cloud_assignment=lambda cloud: assignment,
    )


def patch_env(monkeypatch, app):
    flask_app, root = app
    monkeypatch.setattr(instack_module, "WEB_CONTENT_PATH", str(root))
    monkeypatch.setattr(instack_module, "quads", make_quads(None, ASSIGNMENT))
    return flask_app


def patch_session_user(monkeypatch, email, roles=None):
    monkeypatch.setattr(
        instack_module,
        "current_user",
        SimpleNamespace(is_authenticated=True, email=email, roles=roles or []),
    )


def patch_anonymous(monkeypatch):
    monkeypatch.setattr(instack_module, "current_user", SimpleNamespace(is_authenticated=False))


def test_anonymous_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_anonymous(monkeypatch)
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 401


def test_owner_session_served(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "alice@example.com")
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200
    assert resp.content_type == "application/json"
    assert resp.get_data(as_text=True) == FILE_CONTENT


def test_ccuser_session_served(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "bob@example.com")
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200


def test_ccuser_email_localpart_served(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "carol@example.com")
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200


def test_admin_session_served(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "zed@example.com", roles=["admin"])
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200


def test_non_owner_session_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "mallory@example.com", roles=["user"])
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 403


def test_token_owner_served(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    token_user = {"email": "alice@example.com", "roles": ["user"]}
    monkeypatch.setattr(instack_module, "quads", make_quads(token_user, ASSIGNMENT))
    resp = flask_app.test_client().get(
        "/instack/cloud02_instackenv.json", headers={"Authorization": "Bearer owner_token"}
    )
    assert resp.status_code == 200


def test_invalid_token_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    monkeypatch.setattr(instack_module, "quads", make_quads(None, ASSIGNMENT))
    resp = flask_app.test_client().get(
        "/instack/cloud02_instackenv.json", headers={"Authorization": "Bearer bad_token"}
    )
    assert resp.status_code == 401


def test_token_non_owner_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    token_user = {"email": "mallory@example.com", "roles": ["user"]}
    monkeypatch.setattr(instack_module, "quads", make_quads(token_user, ASSIGNMENT))
    resp = flask_app.test_client().get(
        "/instack/cloud02_instackenv.json", headers={"Authorization": "Bearer non_owner"}
    )
    assert resp.status_code == 403


def test_malformed_authorization_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_anonymous(monkeypatch)
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json", headers={"Authorization": "Bearer"})
    assert resp.status_code == 401


def test_unknown_file_pattern_404_for_owner(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "alice@example.com")
    assert flask_app.test_client().get("/instack/random.txt").status_code == 404
    assert flask_app.test_client().get("/instack/cloud02_other.json").status_code == 404


def test_unknown_file_pattern_404_anonymous(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_anonymous(monkeypatch)
    assert flask_app.test_client().get("/instack/random.txt").status_code == 404


def test_missing_file_404_for_owner(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "alice@example.com")
    resp = flask_app.test_client().get("/instack/cloud02_ocpinventory.json")
    assert resp.status_code == 404


class SummaryReportStub:
    def __init__(self):
        self.calls = []

    async def get_cloud_summary_report(self, username=None, roles=None):
        self.calls.append((username, roles))
        if username is None:
            return {"all_assignments": []}
        return {"my_assignments": [], "other_assignments": [{"name": "cloud02"}]}


def test_summary_route_forwards_identity(app, monkeypatch):
    from quads.web.blueprints import wiki as wiki_module

    flask_app, _ = app
    stub = SummaryReportStub()
    monkeypatch.setattr(wiki_module, "cloud_operation", stub)
    monkeypatch.setattr(
        wiki_module,
        "current_user",
        SimpleNamespace(is_authenticated=True, email="alice@example.com", roles=["user"]),
    )
    resp = flask_app.test_client().get("/summary")
    assert resp.status_code == 200
    assert stub.calls == [("alice", ["user"])]
    assert resp.get_json() == {"my_assignments": [], "other_assignments": [{"name": "cloud02"}]}


def test_summary_route_anonymous(app, monkeypatch):
    from quads.web.blueprints import wiki as wiki_module

    flask_app, _ = app
    stub = SummaryReportStub()
    monkeypatch.setattr(wiki_module, "cloud_operation", stub)
    monkeypatch.setattr(wiki_module, "current_user", SimpleNamespace(is_authenticated=False))
    resp = flask_app.test_client().get("/summary")
    assert resp.status_code == 200
    assert stub.calls == [(None, None)]
    assert resp.get_json() == {"all_assignments": []}


def test_unknown_cloud_404_for_owner(app, monkeypatch):
    from quads.quads_api import APIBadRequest

    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "alice@example.com")

    def raise_bad_request(cloud):
        raise APIBadRequest(f"Cloud not found: {cloud}")

    monkeypatch.setattr(
        instack_module,
        "quads",
        SimpleNamespace(get_active_cloud_assignment=raise_bad_request),
    )
    resp = flask_app.test_client().get("/instack/cloud99_instackenv.json")
    assert resp.status_code == 404


def test_no_assignment_non_admin_403(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    monkeypatch.setattr(instack_module, "quads", make_quads(None, None))
    patch_session_user(monkeypatch, "mallory@example.com", roles=["user"])
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 403


def test_no_assignment_admin_200(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    monkeypatch.setattr(instack_module, "quads", make_quads(None, None))
    patch_session_user(monkeypatch, "zed@example.com", roles=["admin"])
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200


def test_non_bearer_header_rejected(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_anonymous(monkeypatch)
    resp = flask_app.test_client().get(
        "/instack/cloud02_instackenv.json", headers={"Authorization": "Basic dXNlcjpwYXNz"}
    )
    assert resp.status_code == 401


def test_retention_filename_served_for_owner(app, monkeypatch):
    flask_app, root = app
    monkeypatch.setattr(instack_module, "WEB_CONTENT_PATH", str(root))
    monkeypatch.setattr(instack_module, "quads", make_quads(None, ASSIGNMENT))
    patch_session_user(monkeypatch, "alice@example.com")
    retention = os.path.join(str(root), "instack", "cloud02_instackenv.json_2026-08-25_12:00:00")
    with open(retention, "w") as f:
        f.write(FILE_CONTENT)
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json_2026-08-25_12:00:00")
    assert resp.status_code == 200


def test_owner_username_case_insensitive(app, monkeypatch):
    flask_app = patch_env(monkeypatch, app)
    patch_session_user(monkeypatch, "ALICE@example.com")
    resp = flask_app.test_client().get("/instack/cloud02_instackenv.json")
    assert resp.status_code == 200
