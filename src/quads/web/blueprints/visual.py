import asyncio
import os

from flask import Blueprint, abort, render_template

from quads.config import Config
from quads.tools.external.foreman import Foreman
from quads.quads_api import QuadsApi as Quads
from quads.web.blueprints.common import WEB_CONTENT_PATH, get_file_paths

TEMPLATE_DIR = os.path.join(WEB_CONTENT_PATH, "visual")
visual_bp = Blueprint(
    "visual",
    __name__,
    template_folder=TEMPLATE_DIR,
)

quads = Quads(Config)
loop = asyncio.new_event_loop()
foreman = Foreman(
    Config["foreman_api_url"],
    Config["foreman_username"],
    Config["foreman_password"],
    loop=loop,
)


@visual_bp.route("/")
def index():
    try:
        return render_template("index.html")
    except Exception as e:
        return str(e), 500


@visual_bp.route("/<when>")
def visuals(when):
    path = os.path.join(WEB_CONTENT_PATH, "visual")
    file_paths = get_file_paths(path)
    for file in file_paths:
        if when in file:
            return render_template(file)
    return abort(404)
