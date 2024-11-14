import os

from flask import Blueprint, abort, make_response, render_template, send_from_directory

from quads.web.blueprints.common import WEB_CONTENT_PATH, get_file_paths

TEMPLATE_DIR = os.path.join(WEB_CONTENT_PATH, "instack")
instack_bp = Blueprint(
    "instack",
    __name__,
    template_folder=TEMPLATE_DIR,
)


@instack_bp.route("/<cloud>")
def instack(cloud):
    path = os.path.join(WEB_CONTENT_PATH, "instack")
    file_paths = get_file_paths(path)
    for file in file_paths:
        if cloud in file:
            response = make_response(send_from_directory(path, file))
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
    return abort(404)
