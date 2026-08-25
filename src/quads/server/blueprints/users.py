import re

from flask import Blueprint, Response, jsonify, make_response, request

from quads.config import Config
from quads.helpers.timeutil import format_http_date
from quads.server.blueprints import check_access, is_valid_domain
from quads.server.dao.baseDao import EntryNotFound
from quads.server.dao.user import UserDao

user_bp = Blueprint("users", __name__)

VALID_SSH_KEY_PREFIXES = (
    "ssh-rsa",
    "ssh-ed25519",
    "ssh-dss",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
)


def _validate_ssh_key(ssh_key):
    if not ssh_key:
        return None
    ssh_key = ssh_key.strip()
    if not ssh_key.startswith(VALID_SSH_KEY_PREFIXES):
        return "Invalid SSH key format. Key must start with a valid type (e.g. ssh-ed25519, ssh-rsa)."
    parts = ssh_key.split()
    if len(parts) < 2:
        return "Invalid SSH key format. Expected: type base64-data [comment]"
    return None


RELEASE_CMD_MAX_LENGTH = 1024

BLOCKED_PATTERNS = [
    r"(?:^|[;&|]\s*)rm\s+.*-[rR].*\s+/",
    r":\(\)\s*\{\s*:\|:\s*&\s*\}\s*;",
    r"(?:^|[;&|]\s*)dd\s+.*of=/dev/",
    r"(?:^|[;&|]\s*)mkfs",
    r"(?:^|[;&|]\s*)shutdown",
    r"(?:^|[;&|]\s*)reboot",
    r"(?:^|[;&|]\s*)halt",
    r"(?:^|[;&|]\s*)poweroff",
    r"(?:^|[;&|]\s*)init\s+[06]",
    r"(?:^|[;&|]\s*)systemctl\s+reboot",
]


def _validate_release_command(command):
    if not command:
        return None
    if len(command) > RELEASE_CMD_MAX_LENGTH:
        return f"Command exceeds {RELEASE_CMD_MAX_LENGTH} character limit."
    cleaned = re.sub(r"[^\x09\x0a\x0d\x20-\x7e]", "", command)
    if cleaned != command:
        return "Command contains invalid control characters."
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return "Command contains a blocked operation."
    return None


def _user_to_dict(user):
    return {
        "id": user.id,
        "email": user.email,
        "google_id": user.google_id,
        "profile_picture": user.profile_picture,
        "active": user.active,
        "last_login": format_http_date(user.last_login) if user.last_login else None,
        "roles": [role.name for role in user.roles],
        "ssh_key": user.ssh_key,
        "release_command": user.release_command,
    }


@user_bp.route("/")
@check_access(["admin"])
def get_users() -> Response:
    google_id = request.args.get("google_id")
    if google_id:
        user = UserDao.get_user_by_google_id(google_id)
        if not user:
            return make_response(jsonify(None), 200)
        return jsonify(_user_to_dict(user))

    return make_response(jsonify({"message": "Query parameter required"}), 400)


@user_bp.route("/<path:email>")
@check_access(["admin"])
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
@check_access(["admin"])
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

    if "ssh_key" in data and data["ssh_key"]:
        error = _validate_ssh_key(data["ssh_key"])
        if error:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": error,
            }
            return make_response(jsonify(response), 400)

    if "release_command" in data and data["release_command"]:
        error = _validate_release_command(data["release_command"])
        if error:
            response = {
                "status_code": 400,
                "error": "Bad Request",
                "message": error,
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
