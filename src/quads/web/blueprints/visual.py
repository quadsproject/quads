import os

from flask import Blueprint, abort, render_template

from quads.config import Config
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


@visual_bp.route("/<when>")
async def visuals(when):
    file_paths = get_file_paths(VISUAL_DIR)
    for file in file_paths:
        if when in file:
            with open(os.path.join(VISUAL_DIR, file), "r") as f:
                html_content = f.read()
            return render_template("wiki/visuals.html", html_content=html_content)
    return abort(404)
