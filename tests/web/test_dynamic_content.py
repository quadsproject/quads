import pytest

import quads.web.app as web_app_module
import quads.web.blueprints.common as common_module
from quads.web.app import create_app
from quads.web.blueprints import dynamic_content as dynamic_content_module


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    root = tmp_path_factory.mktemp("web_content")
    (root / "index.html").write_text("root page")
    (root / "sub").mkdir()
    (root / "sub" / "index.html").write_text("sub page")
    (root / "static").mkdir()
    (root / "static" / "file.css").write_text("body{}")
    (root / "instack").mkdir()
    (root / "instack" / "cloud02_instackenv.json").write_text('{"nodes": []}')
    original_app_web_content = web_app_module.WEB_CONTENT_PATH
    web_app_module.WEB_CONTENT_PATH = str(root)
    original_template_folder = dynamic_content_module.dynamic_content_bp.template_folder
    dynamic_content_module.dynamic_content_bp.template_folder = str(root)
    original_static_folder = dynamic_content_module.dynamic_content_bp.static_folder
    dynamic_content_module.dynamic_content_bp.static_folder = str(root / "static")
    try:
        flask_app = create_app()
        yield flask_app, root
    finally:
        dynamic_content_module.dynamic_content_bp.template_folder = original_template_folder
        dynamic_content_module.dynamic_content_bp.static_folder = original_static_folder
        web_app_module.WEB_CONTENT_PATH = original_app_web_content


def patch_web_content(monkeypatch, app):
    flask_app, root = app
    monkeypatch.setattr(common_module, "EXCLUDE_DIRS", [".git", "static", "instack", "visual"])
    monkeypatch.setattr(common_module, "WEB_CONTENT_PATH", str(root))
    monkeypatch.setattr(dynamic_content_module, "WEB_CONTENT_PATH", str(root))
    monkeypatch.setattr(common_module.get_file_paths, "__defaults__", (str(root),))
    return flask_app


def test_root_page_served(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    resp = flask_app.test_client().get("/index")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "root page"


def test_subdir_page_served(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    resp = flask_app.test_client().get("/sub/index")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "sub page"


def test_parent_traversal_returns_404(app, monkeypatch):
    # GET /../index reaches the two-segment route with directory='..',
    # exercising the safe_join guard (404 instead of the pre-fix 500).
    flask_app = patch_web_content(monkeypatch, app)
    resp = flask_app.test_client().get("/../index")
    assert resp.status_code == 404


def test_encoded_parent_traversal_returns_404(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    resp = flask_app.test_client().get("/..%2findex")
    assert resp.status_code == 404
    resp = flask_app.test_client().get("/..%5cindex")
    assert resp.status_code == 404


def test_unknown_pages_404(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    assert flask_app.test_client().get("/doesnotexist").status_code == 404
    assert flask_app.test_client().get("/sub/doesnotexist").status_code == 404
    assert flask_app.test_client().get("/other/index").status_code == 404


def test_instack_payload_not_servable(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    assert flask_app.test_client().get("/cloud02_instackenv").status_code == 404


def test_content_static_still_served(app, monkeypatch):
    flask_app = patch_web_content(monkeypatch, app)
    resp = flask_app.test_client().get("/content/file.css")
    assert resp.status_code == 200
    assert resp.get_data(as_text=True) == "body{}"
