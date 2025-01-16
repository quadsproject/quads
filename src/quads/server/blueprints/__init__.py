import json
from functools import wraps

from flask import Response, request, g

from quads.server.models import Role, User, db


def check_access(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Response:
            if "Authorization" in request.headers:
                auth_value = request.headers["Authorization"].split(" ")
                if len(auth_value) < 2:
                    response = {
                        "message": "Authorization header malformed",
                        "error": "Bad Request",
                    }
                    return Response(response=json.dumps(response), status=400)

                if auth_value[0].lower() == "bearer":
                    try:
                        username = User.decode_auth_token(auth_value[1])
                        current_user = db.session.query(User).filter(User.email == username).first()
                        if current_user is None:
                            response = {
                                "message": "Invalid Authentication token!",
                                "error": "Unauthorized",
                            }
                            return Response(response=json.dumps(response), status=401)
                        if not current_user.active:
                            response = {
                                "message": "You don't have the permission to access the requested resource",
                                "error": "Forbidden",
                            }
                            return Response(response=json.dumps(response), status=403)
                    except Exception as e:
                        response = {
                            "message": "Something went wrong",
                            "error": str(e),
                        }
                        return Response(response=json.dumps(response), status=500)

                if auth_value[0].lower() == "basic":
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

                has_role = False
                for role in roles:
                    role_obj = db.session.query(Role).filter(Role.name == role).first()
                    if role_obj in current_user.roles:
                        has_role = True
                if not has_role:
                    response = {
                        "message": "You don't have the permission to access the requested resource",
                        "error": "Forbidden",
                    }
                    return Response(response=json.dumps(response), status=403)
            else:
                response = {
                    "message": "Missing authentication data",
                    "error": "Bad Request",
                }
                return Response(response=json.dumps(response), status=400)
            g.current_user = current_user
            return f(*args, **kwargs)

        return decorated_function

    return decorator
