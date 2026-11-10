from types import SimpleNamespace

import pytest

import quads.web.app as web_app
import quads.web.blueprints.wiki as wiki_module
from quads.web.app import create_app

ANONYMOUS_HEADERS = 'const headers = ["NAME", "SUMMARY", "OWNER", "REQUEST", "STATUS"];'
AUTHENTICATED_HEADERS = 'const headers = ["NAME", "SUMMARY", "OWNER", "REQUEST", "STATUS", "OSPENV", "OCPENV"];'


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    original = web_app.WEB_CONTENT_PATH
    web_app.WEB_CONTENT_PATH = str(tmp_path_factory.mktemp("web_content"))
    try:
        yield create_app()
    finally:
        web_app.WEB_CONTENT_PATH = original


def request_page(app, monkeypatch, authenticated):
    monkeypatch.setattr(wiki_module, "current_user", SimpleNamespace(is_authenticated=authenticated))
    return app.test_client().get("/assignments/")


def test_anonymous_hides_environment_columns(app, monkeypatch):
    body = request_page(app, monkeypatch, authenticated=False).get_data(as_text=True)

    assert ANONYMOUS_HEADERS in body
    assert "OSPENV" not in body
    assert "OCPENV" not in body
    assert "OCPINV" not in body
    assert "const show_env_columns = false;" in body


def test_authenticated_shows_environment_columns(app, monkeypatch):
    body = request_page(app, monkeypatch, authenticated=True).get_data(as_text=True)

    assert AUTHENTICATED_HEADERS in body
    assert "const show_env_columns = true;" in body
    assert "OCPINV" not in body
