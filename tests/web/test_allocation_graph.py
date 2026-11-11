import os

import pytest

import quads.web.app as web_app_module
import quads.web.blueprints.visual as visual_module
from quads.web.app import create_app


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    original = visual_module.VISUAL_DIR
    original_web_content = web_app_module.WEB_CONTENT_PATH
    visual_module.VISUAL_DIR = str(tmp_path_factory.mktemp("visual"))
    web_app_module.WEB_CONTENT_PATH = str(tmp_path_factory.mktemp("web_content"))
    try:
        yield create_app()
    finally:
        visual_module.VISUAL_DIR = original
        web_app_module.WEB_CONTENT_PATH = original_web_content


def test_graph_served(app):
    path = os.path.join(visual_module.VISUAL_DIR, "allocation-graphic.html")
    with open(path, "w") as handle:
        handle.write("<div id='graph'>ok</div>")
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 200
    assert "<div id='graph'>ok</div>" in response.get_data(as_text=True)


def test_graph_missing_returns_404(app):
    path = os.path.join(visual_module.VISUAL_DIR, "allocation-graphic.html")
    if os.path.exists(path):
        os.remove(path)
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 404
    assert "Allocation graphic has not been generated" in response.get_data(as_text=True)
