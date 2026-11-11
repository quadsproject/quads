import os

import pytest

import quads.web.app as web_app_module
import quads.web.blueprints.visual as visual_module
from quads.tools.allocation_graph import GRAPH_FILENAME, GRAPH_SUBDIR
from quads.web.app import create_app


def _graph_path():
    graph_dir = os.path.join(visual_module.VISUAL_DIR, GRAPH_SUBDIR)
    os.makedirs(graph_dir, exist_ok=True)
    return os.path.join(graph_dir, GRAPH_FILENAME)


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
    path = _graph_path()
    with open(path, "w") as handle:
        handle.write("<div id='graph'>ok</div>")
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "<div id='graph'>ok</div>" in body
    assert '<h2 class="mb-3"><b>Allocation Graphic</b></h2>' in body
    assert "Monthly Usage" not in body
    assert 'href="/visual/graph"' in body


def test_graph_missing_returns_404(app):
    path = _graph_path()
    if os.path.exists(path):
        os.remove(path)
    response = app.test_client().get("/visual/graph")
    assert response.status_code == 404
    assert "Allocation graphic has not been generated" in response.get_data(as_text=True)


def test_visuals_route_skips_graph_subdir_basename(app):
    # Regression: get_file_paths walks into graph/ and yields the bare basename,
    # so /visual/allocation-graphic matched it and opened the missing top-level
    # file, 500ing.  It must fall through to 404, not raise.
    path = _graph_path()
    with open(path, "w") as handle:
        handle.write("<div>graph</div>")
    response = app.test_client().get("/visual/allocation-graphic")
    assert response.status_code == 404


def test_graph_directory_returns_404(app):
    path = _graph_path()
    if os.path.exists(path):
        os.remove(path)
    os.mkdir(path)
    try:
        response = app.test_client().get("/visual/graph")
        assert response.status_code == 404
        assert "Allocation graphic has not been generated" in response.get_data(as_text=True)
    finally:
        os.rmdir(path)
