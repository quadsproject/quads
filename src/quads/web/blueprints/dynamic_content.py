import os

from flask import Blueprint, abort, render_template
from jinja2 import TemplateNotFound
from werkzeug.utils import safe_join

from quads.web.blueprints.common import WEB_CONTENT_PATH, get_file_paths

STATIC_DIR = os.path.join(WEB_CONTENT_PATH, "static")
dynamic_content_bp = Blueprint(
    "content",
    __name__,
    template_folder=WEB_CONTENT_PATH,
    static_folder=STATIC_DIR,
    static_url_path="/content",
)


@dynamic_content_bp.route("/<page>")
async def dynamic_content(page):
    file_paths = get_file_paths()
    for file in file_paths:
        if page in file:
            try:
                return render_template(file)
            except TemplateNotFound:
                return abort(404)
    return abort(404)


@dynamic_content_bp.route("/<directory>/<page>")
async def dynamic_content_sub(directory, page):
    file_paths = get_file_paths()
    for file in file_paths:
        if page in file:
            template = safe_join(WEB_CONTENT_PATH, directory, file)
            if template is None:
                return abort(404)
            try:
                return render_template(os.path.relpath(template, WEB_CONTENT_PATH))
            except TemplateNotFound:
                return abort(404)
    return abort(404)
