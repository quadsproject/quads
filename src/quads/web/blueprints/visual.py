import os

from flask import Blueprint, abort, render_template

from quads.config import Config
from quads.tools.allocation_graph import GRAPH_FILENAME, GRAPH_SUBDIR
from quads.web.blueprints.common import WEB_CONTENT_PATH, get_file_paths

VISUAL_DIR = Config.get("visual_web_dir")
visual_bp = Blueprint(
    "visual",
    __name__,
    template_folder=WEB_CONTENT_PATH,
)


@visual_bp.route("/")
async def index():
    with open(os.path.join(VISUAL_DIR, "index.html"), "r") as f:
        html_content = f.read()
    return render_template("wiki/visuals.html", html_content=html_content)


@visual_bp.route("/graph")
async def graph():
    file_path = os.path.join(VISUAL_DIR, GRAPH_SUBDIR, GRAPH_FILENAME)
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html_content = f.read()
    except OSError:
        abort(404, description="Allocation graphic has not been generated")
    return render_template("wiki/allocation_graph.html", html_content=html_content)


@visual_bp.route("/<when>")
async def visuals(when):
    file_paths = get_file_paths(VISUAL_DIR)
    for file in file_paths:
        if when in file:
            # get_file_paths walks recursively and yields bare basenames, so a
            # file in a subdir (e.g. graph/allocation-graphic.html) matches here
            # but does not exist at the top level.  Skip it instead of 500ing;
            # os.walk is top-down, so a real top-level match is served first.
            try:
                with open(os.path.join(VISUAL_DIR, file), "r") as f:
                    html_content = f.read()
            except OSError:
                continue
            return render_template("wiki/visuals.html", html_content=html_content)
    return abort(404)
