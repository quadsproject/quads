import json

from flask import Blueprint, Response, jsonify, make_response, request
from validators import email

from quads.server.app import basic_auth, user_datastore
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
    if not user:
        try:
            user = user_datastore.create_user(email=data["email"], password=data["password"], roles=[role])
            db.session.commit()
            auth_token = User.encode_auth_token(user.id)
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
        auth_token = User.encode_auth_token(user.email)
        if auth_token:
            response_object = {
                "status_code": 201,
                "status": "success",
                "message": "Successful login",
                "auth_token": auth_token,
            }
            return jsonify(response_object)
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


@auth_bp.route("/resetpassword/", methods=["POST"])
def reset_password() -> Response:
    """
    Used to initiate password reset for a user.
        It takes in the email address as JSON input, validates it,
        and generates a temporary password reset token.
        In a production environment, this would send an email with the reset link.

    :return: A json response with success message
    """
    import secrets
    import string
    from datetime import datetime, timedelta

    data = request.get_json()
    if not data or not data.get("email"):
        response = {
            "status_code": 400,
            "status": "fail",
            "message": "Email address is required.",
        }
        return Response(response=json.dumps(response), status=400)

    email_address = data.get("email")
    if not email(email_address):
        response = {
            "status_code": 400,
            "status": "fail",
            "message": "Invalid email address.",
        }
        return Response(response=json.dumps(response), status=400)

    try:
        user = user_datastore.find_user(email=email_address)
        if not user:
            # For security, we don't reveal if user exists or not
            response = {
                "status_code": 200,
                "status": "success",
                "message": "If the email address exists, a password reset link has been sent.",
            }
            return jsonify(response)

        # Generate a temporary password reset token
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)  # Token expires in 1 hour

        # Store the reset token in the database
        from quads.server.models import PasswordResetToken, db

        # Clean up any existing tokens for this user
        db.session.query(PasswordResetToken).filter_by(user_id=user.id).delete()

        # Create new reset token
        password_reset_token = PasswordResetToken(user_id=user.id, token=reset_token, expires_at=expires_at)
        db.session.add(password_reset_token)
        db.session.commit()

        # Send password reset email
        from quads.config import Config
        from quads.tools.external.postman import Postman

        # Generate reset URL
        reset_url = f"{Config['quads_base_url']}reset-password?token={reset_token}"

        # Create email content
        subject = "Password Reset Request"
        content = f"""
Hello,

You have requested to reset your password for your QUADS account.

Please click the following link to reset your password:
{reset_url}

This link will expire in 1 hour.

If you did not request this password reset, please ignore this email.

Best regards,
QUADS Team
"""

        # Extract username from email (part before @)
        username = email_address.split("@")[0]

        # Send email using Postman
        postman = Postman(subject=subject, to=username, cc=[], content=content)  # Postman will add the domain

        email_sent = postman.send_email()

        if email_sent:
            response = {
                "status_code": 200,
                "status": "success",
                "message": "If the email address exists, a password reset link has been sent.",
            }
        else:
            response = {
                "status_code": 500,
                "status": "fail",
                "message": "Error sending password reset email.",
            }

        return jsonify(response)

    except Exception:
        response = {
            "status_code": 500,
            "status": "fail",
            "message": "Error processing password reset request.",
        }
        return Response(response=json.dumps(response), status=500)


@auth_bp.route("/confirmresetpassword/", methods=["POST"])
def confirm_reset_password() -> Response:
    """
    Used to complete password reset with a valid token.
        It takes in the reset token and new password as JSON input,
        validates the token, and updates the user's password.

    :return: A json response with success/failure message
    """
    data = request.get_json()
    if not data or not data.get("token") or not data.get("password"):
        response = {
            "status_code": 400,
            "status": "fail",
            "message": "Reset token and new password are required.",
        }
        return Response(response=json.dumps(response), status=400)

    reset_token = data.get("token")
    new_password = data.get("password")

    try:
        from quads.server.models import PasswordResetToken, db

        # Find the reset token
        token_record = db.session.query(PasswordResetToken).filter_by(token=reset_token).first()

        if not token_record or not token_record.is_valid():
            response = {
                "status_code": 400,
                "status": "fail",
                "message": "Invalid or expired reset token.",
            }
            return Response(response=json.dumps(response), status=400)

        # Update the user's password
        user = token_record.user
        user.password = new_password  # This will be hashed by the model

        # Mark the token as used
        token_record.used = True

        db.session.commit()

        response = {
            "status_code": 200,
            "status": "success",
            "message": "Password has been reset successfully.",
        }
        return jsonify(response)

    except Exception:
        response = {
            "status_code": 500,
            "status": "fail",
            "message": "Error processing password reset.",
        }
        return Response(response=json.dumps(response), status=500)
