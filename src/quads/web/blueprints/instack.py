import os

from flask import Blueprint, abort, make_response

from quads.web.blueprints.common import WEB_CONTENT_PATH

TEMPLATE_DIR = os.path.join(WEB_CONTENT_PATH, "instack")
instack_bp = Blueprint(
    "instack",
    __name__,
    template_folder=TEMPLATE_DIR,
)


@instack_bp.route("/<file>")
async def instack(file):
    path = os.path.join(WEB_CONTENT_PATH, "instack")
    file_path = os.path.join(path, file)
    if not os.path.exists(file_path):
        return abort(404)

    with open(file_path, "r") as f:
        content = f.read()

    response = make_response(content)
    response.headers["Content-Type"] = "application/json"
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
