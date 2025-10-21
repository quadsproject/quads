import json
import hmac
import hashlib

from datetime import datetime
from functools import wraps
from flask import Response, request, current_app

from quads.server.models import Role, User, db, PersonalAccessToken


def _pat_digest(value: str) -> str:
    secret = current_app.config["SECRET_KEY"].encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def check_access(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Response:
            if "Authorization" not in request.headers:
                return Response(
                    response=json.dumps({"message": "Missing authentication data", "error": "Bad Request"}), status=400
                )

            auth_value = request.headers["Authorization"].split(" ")
            if len(auth_value) < 2:
                return Response(
                    response=json.dumps({"message": "Authorization header malformed", "error": "Bad Request"}),
                    status=400,
                )

            scheme, token = auth_value[0].lower(), auth_value[1]
            current_user = None

            if scheme == "bearer":
                try:
                    username = User.decode_auth_token(token)
                    current_user = db.session.query(User).filter(User.email == username).first()
                except Exception:
                    # Fallback to PAT
                    digest = _pat_digest(token)
                    pat = (
                        db.session.query(PersonalAccessToken)
                        .filter(
                            PersonalAccessToken.digest == digest,
                            PersonalAccessToken.revoked_at.is_(None),
                        )
                        .first()
                    )
                    if pat:
                        # expiry check
                        if pat.expires_at and pat.expires_at < datetime.utcnow():
                            pat = None
                        else:
                            current_user = db.session.query(User).get(pat.user_id)
                            pat.last_used_at = datetime.utcnow()
                            db.session.commit()

                if not current_user or not current_user.active:
                    return Response(
                        response=json.dumps({"message": "Invalid Authentication token!", "error": "Unauthorized"}),
                        status=401,
                    )

            elif scheme == "basic":
                username = request.authorization["username"]
                password = request.authorization["password"]
                current_user = db.session.query(User).filter(User.email == username).first()
                if current_user is None:
                    response = {
                        "message": "Invalid Credentials!",
                        "error": "Unauthorized",
                    }
                    return Response(response=json.dumps(response), status=401)
                if not current_user.verify_password(password):
                    response = {
                        "message": "Invalid Credentials!",
                        "error": "Unauthorized",
                    }
                    return Response(response=json.dumps(response), status=401)

            # role check
            has_role = any(db.session.query(Role).filter(Role.name == r).first() in current_user.roles for r in roles)
            if not has_role:
                return Response(
                    response=json.dumps(
                        {
                            "message": "You don't have the permission to access the requested resource",
                            "error": "Forbidden",
                        }
                    ),
                    status=403,
                )

            # make current_user available to views without importing flask.g everywhere
            request.ctx = getattr(request, "ctx", type("obj", (), {})())
            request.ctx.current_user = current_user
            return f(*args, **kwargs)

        return decorated_function

    return decorator
