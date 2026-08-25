import os

from flask import Blueprint, abort, make_response, request
from flask_login import current_user

from quads.config import Config
from quads.quads_api import APIBadRequest, QuadsApi
from quads.web.auth_helpers import get_username_from_email, is_cloud_owner
from quads.web.blueprints.common import WEB_CONTENT_PATH, extract_cloud_from_instack_file

TEMPLATE_DIR = os.path.join(WEB_CONTENT_PATH, "instack")
instack_bp = Blueprint(
    "instack",
    __name__,
    template_folder=TEMPLATE_DIR,
)

quads = QuadsApi(Config)


@instack_bp.route("/<file>")
async def instack(file):
    cloud_name = extract_cloud_from_instack_file(file)
    if not cloud_name:
        return abort(404)

    if "Authorization" in request.headers:
        auth_value = request.headers["Authorization"].split(" ")
        if len(auth_value) < 2 or auth_value[0].lower() != "bearer":
            return abort(401)
        user = quads.get_authenticated_user(auth_value[1])
        if user is None:
            return abort(401)
        username = get_username_from_email(user["email"])
        roles = user["roles"]
    elif current_user.is_authenticated:
        username = get_username_from_email(current_user.email)
        roles = current_user.roles
    else:
        return abort(401)

    try:
        assignment = quads.get_active_cloud_assignment(cloud_name)
    except APIBadRequest:
        return abort(404)
    owner = assignment.owner if assignment else None
    ccuser = assignment.ccuser if assignment else None
    if not is_cloud_owner(username, owner, ccuser, roles):
        return abort(403)

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
