import json

from flask import Blueprint, Response, g, jsonify, make_response, request
from validators import email

from quads.config import Config
from quads.server.app import basic_auth, user_datastore
from quads.server.blueprints import check_access, is_valid_domain
from quads.server.models import Role, TokenBlackList, User, db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register/", methods=["POST"])
def register() -> Response:
    """
    Used to register a new user.
        It takes in the email and password of the user as JSON input, validates it,
        creates a new User object with that data and saves it to the database.
        If successful, an auth token is generated for that user and returned along with a success message.

    :return: A json response with the auth token:
    """
    if Config.get("require_auth_provider", False):
        response = {
            "status_code": 403,
            "status": "fail",
            "message": "Self-registration is disabled. Contact an administrator or use SSO.",
        }
        return Response(response=json.dumps(response), status=403)

    data = request.get_json()
    user = user_datastore.find_user(email=data.get("email"))
    role = db.session.query(Role).filter(Role.name == "user").first()
    if not data["email"] or not data["password"]:
        response = {
            "status_code": 401,
            "status": "fail",
            "message": "Please provide both email and password.",
        }
        return Response(response=json.dumps(response), status=401)
    if not email(data["email"]):
        response = {
            "status_code": 401,
            "status": "fail",
            "message": "Invalid email address.",
        }
        return Response(response=json.dumps(response), status=401)
    if not is_valid_domain(data["email"]):
        response = {
            "status_code": 403,
            "status": "fail",
            "message": f"Registration restricted to @{Config['domain']} addresses.",
        }
        return Response(response=json.dumps(response), status=403)
    if not user:
        try:
            user = user_datastore.create_user(email=data["email"], password=data["password"], roles=[role])
            db.session.commit()
            auth_token = User.encode_auth_token(user.email, role.name)
            response_object = {
                "status": "success",
                "status_code": 200,
                "message": "Successfully registered",
                "auth_token": auth_token,
            }
            return jsonify(response_object)
        except Exception:
            response = {
                "status_code": 401,
                "status": "fail",
                "message": "An error occurred. Please try again.",
            }
            return Response(response=json.dumps(response), status=401)
    else:
        if user._password is None:
            user.password = data["password"]
            db.session.commit()
            user_role = user.roles[0].name if user.roles else "user"
            auth_token = User.encode_auth_token(user.email, user_role)
            response_object = {
                "status": "success",
                "status_code": 200,
                "message": "Password set on existing account",
                "auth_token": auth_token,
            }
            return jsonify(response_object)
        response = {
            "status_code": 401,
            "status": "fail",
            "message": "User already exists. Please Log in.",
        }
        return Response(response=json.dumps(response), status=401)


@auth_bp.route("/login/", methods=["POST"])
@basic_auth.login_required
def login() -> Response:
    """
    Used to authenticate a user.
        It takes in the email and password of the user, and returns an auth token if successful.
        If unsuccessful, it returns a 401 error code.

    :return: A json object with a status code, status, message and auth_token
    """
    try:
        current_user = basic_auth.username()
        user = db.session.query(User).filter(User.email == current_user).first()
        user_role = user.roles[0].name if user.roles else None
        auth_token = User.encode_auth_token(user.email, user_role)
        if auth_token:
            response_object = {
                "status_code": 201,
                "status": "success",
                "message": "Successful login",
                "auth_token": auth_token,
            }
            return make_response(jsonify(response_object), 201)
        else:
            response = {
                "status_code": 401,
                "status": "fail",
                "message": "User does not exist.",
            }
            return Response(response=json.dumps(response), status=401)
    except Exception:
        response = {"status_code": 500, "status": "fail", "message": "Try again"}
        return Response(response=json.dumps(response), status=500)


@auth_bp.route("/logout/", methods=["POST"])
def logout() -> Response:
    # get auth token
    """
    Used to logout a user.
        It takes in the Authorization header and checks if it exists. If it exists we add this auth token into our
        blacklist table

    :return: A response object
    """
    auth_header = request.headers.get("Authorization")
    if auth_header:
        auth_token = auth_header.split(" ")[1]
    else:
        auth_token = ""
    if auth_token:
        resp = User.decode_auth_token(auth_token)
        user = user_datastore.find_user(email=resp)
        if user:
            token_blacklist = TokenBlackList(token=auth_token)
            try:
                db.session.add(token_blacklist)
                db.session.commit()
                response_object = {
                    "status": "success",
                    "message": "Successfully logged out.",
                }
                return jsonify(response_object)
            except Exception as e:
                response = {"status": "fail", "message": f"{str(e)}"}
                return make_response(jsonify(response), 500)
        else:
            response = {"status": "fail", "message": resp}
            return make_response(jsonify(response), 401)
    else:
        response = {
            "status": "fail",
            "message": "Provide a valid auth token.",
        }
        return make_response(jsonify(response), 403)


@auth_bp.route("/me")
@check_access(["admin", "user"])
def me() -> Response:
    return jsonify({"email": g.current_user.email, "roles": [role.name for role in g.current_user.roles]})
