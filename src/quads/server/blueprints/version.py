from flask import Blueprint, Response, jsonify, make_response

from quads.config import Config

version_bp = Blueprint("version", __name__)


@version_bp.route("/")
def get_version() -> Response:
    response = f"QUADS version {Config.QUADSVERSION} {Config.QUADSCODENAME}"
    return make_response(jsonify(response), 200)
