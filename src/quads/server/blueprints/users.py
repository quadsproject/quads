from flask import Blueprint, Response, jsonify, make_response, request

from quads.config import Config
from quads.server.blueprints import is_valid_domain
from quads.server.dao.baseDao import EntryNotFound
from quads.server.dao.user import UserDao

user_bp = Blueprint("users", __name__)


def _user_to_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "google_id": user.google_id,
        "profile_picture": user.profile_picture,
        "active": user.active,
        "last_login": user.last_login.strftime("%a, %d %b %Y %H:%M:%S GMT") if user.last_login else None,
        "roles": [role.name for role in user.roles],
    }


@user_bp.route("/")
def get_users() -> Response:
    google_id = request.args.get("google_id")
    if google_id:
        user = UserDao.get_user_by_google_id(google_id)
        if not user:
            return make_response(jsonify(None), 200)
        return jsonify(_user_to_dict(user))

    return make_response(jsonify({"message": "Query parameter required"}), 400)


@user_bp.route("/<path:email>")
def get_user(email: str) -> Response:
    user = UserDao.get_user_by_email(email)
    if not user:
        return make_response(jsonify(None), 200)
    return jsonify(_user_to_dict(user))


@user_bp.route("/", methods=["POST"])
def create_user() -> Response:
    data = request.get_json()
    if not data or not data.get("email"):
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "Email is required",
        }
        return make_response(jsonify(response), 400)

    if not is_valid_domain(data["email"]):
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": f"Users must have @{Config['domain']} addresses",
        }
        return make_response(jsonify(response), 403)

    existing = UserDao.get_user_by_email(data["email"])
    if existing:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "User already exists",
        }
        return make_response(jsonify(response), 400)

    user = UserDao.create_user(
        email=data["email"],
        google_id=data.get("google_id"),
        profile_picture=data.get("profile_picture"),
        active=data.get("active", True),
        fs_uniquifier=data.get("fs_uniquifier"),
    )
    return make_response(jsonify(_user_to_dict(user)), 201)


@user_bp.route("/<path:email>", methods=["PATCH"])
def update_user(email: str) -> Response:
    if not is_valid_domain(email):
        response = {
            "status_code": 403,
            "error": "Forbidden",
            "message": f"Users must have @{Config['domain']} addresses",
        }
        return make_response(jsonify(response), 403)

    data = request.get_json()
    if not data:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": "No data provided",
        }
        return make_response(jsonify(response), 400)

    try:
        user = UserDao.update_user(email, **data)
    except EntryNotFound:
        response = {
            "status_code": 400,
            "error": "Bad Request",
            "message": f"User not found: {email}",
        }
        return make_response(jsonify(response), 400)

    return jsonify(_user_to_dict(user))
