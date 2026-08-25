from flask import Blueprint, Response, g, jsonify, make_response, request

from quads.helpers.timeutil import format_http_date
from quads.server.blueprints import check_access
from quads.server.dao.api_token import ApiTokenDao
from quads.server.dao.baseDao import EntryNotFound, InvalidArgument
from quads.server.dao.user import UserDao
from quads.server.models import Role, db

api_token_bp = Blueprint("api_tokens", __name__)


def _token_to_dict(token):
    return {
        "id": token.id,
        "name": token.name,
        "token_prefix": token.token_prefix,
        "created_at": format_http_date(token.created_at) if token.created_at else None,
        "last_used": format_http_date(token.last_used) if token.last_used else None,
    }


def _resolve_user(email):
    caller = g.current_user
    admin_role = db.session.query(Role).filter(Role.name == "admin").first()
    is_admin = admin_role in caller.roles

    if not is_admin and caller.email != email:
        return None, make_response(
            jsonify({"status_code": 403, "error": "Forbidden", "message": "Cannot manage tokens for another user"}),
            403,
        )

    user = UserDao.get_user_by_email(email)
    if not user:
        return None, make_response(
            jsonify({"status_code": 404, "error": "Not Found", "message": f"User not found: {email}"}),
            404,
        )
    return user, None


@api_token_bp.route("/<path:email>/")
@check_access(["admin", "user"])
def list_tokens(email) -> Response:
    user, error = _resolve_user(email)
    if error:
        return error
    tokens = ApiTokenDao.get_tokens_by_user(user.id)
    return jsonify([_token_to_dict(t) for t in tokens])


@api_token_bp.route("/<path:email>/", methods=["POST"])
@check_access(["admin", "user"])
def create_token(email) -> Response:
    user, error = _resolve_user(email)
    if error:
        return error

    data = request.get_json()
    name = data.get("name", "").strip() if data else ""
    if not name:
        return make_response(
            jsonify({"status_code": 400, "error": "Bad Request", "message": "Token name is required"}),
            400,
        )
    if len(name) > 256:
        return make_response(
            jsonify(
                {"status_code": 400, "error": "Bad Request", "message": "Token name must be 256 characters or fewer"}
            ),
            400,
        )

    try:
        token, raw_token = ApiTokenDao.create_token(user.id, name)
    except InvalidArgument as ex:
        return make_response(
            jsonify({"status_code": 400, "error": "Bad Request", "message": str(ex)}),
            400,
        )

    result = _token_to_dict(token)
    result["token"] = raw_token
    return make_response(jsonify(result), 201)


@api_token_bp.route("/<path:email>/<int:token_id>", methods=["DELETE"])
@check_access(["admin", "user"])
def delete_token(email, token_id) -> Response:
    user, error = _resolve_user(email)
    if error:
        return error

    try:
        ApiTokenDao.delete_token(token_id, user.id)
    except EntryNotFound:
        return make_response(
            jsonify({"status_code": 404, "error": "Not Found", "message": f"Token not found: {token_id}"}),
            404,
        )

    return jsonify({"status_code": 200, "message": "Token deleted"})
