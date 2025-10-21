import os
import hmac
import hashlib
import base64
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response, current_app
from quads.server.models import db, User, PersonalAccessToken
from quads.server.blueprints import check_access

tokens_bp = Blueprint("tokens", __name__)


def _pat_digest(value: str) -> str:
    secret = current_app.config["SECRET_KEY"].encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def _new_token_value() -> str:
    # URL-safe, no padding, 32 bytes of entropy (~43 chars)
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


@tokens_bp.route("/<email>/tokens", methods=["GET"])
@check_access(["user", "admin"])
def list_tokens(email) -> Response:
    current_user = request.ctx.current_user  # see update to check_access below
    if current_user.email != email and not any(r.name == "admin" for r in current_user.roles):
        return jsonify({"message": "Forbidden"}), 403
    user = db.session.query(User).filter(User.email == email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404
    items = []
    for t in user.personal_tokens.filter(PersonalAccessToken.revoked_at.is_(None)).all():
        items.append(
            {
                "id": t.id,
                "name": t.name,
                "scopes": t.scopes.split(",") if t.scopes else [],
                "created_at": t.created_at.isoformat(),
                "expires_at": t.expires_at.isoformat() if t.expires_at else None,
                "last_used_at": t.last_used_at.isoformat() if t.last_used_at else None,
            }
        )
    return jsonify(items)


@tokens_bp.route("/<email>/tokens", methods=["POST"])
@check_access(["user", "admin"])
def create_token(email) -> Response:
    current_user = request.ctx.current_user
    if current_user.email != email and not any(r.name == "admin" for r in current_user.roles):
        return jsonify({"message": "Forbidden"}), 403

    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name") or "api-token"
    scopes = data.get("scopes", [])
    days = int(data.get("expires_in_days", 0))  # 0 = no expiry

    value = _new_token_value()
    digest = _pat_digest(value)

    user = db.session.query(User).filter(User.email == email).first()
    if not user:
        return jsonify({"message": "User not found"}), 404

    pat = PersonalAccessToken(
        user_id=user.id,
        name=name,
        digest=digest,
        scopes=",".join(scopes),
        expires_at=(datetime.utcnow() + timedelta(days=days)) if days > 0 else None,
    )
    db.session.add(pat)
    db.session.commit()

    # IMPORTANT: return plaintext token ONCE
    return (
        jsonify(
            {
                "token": value,
                "id": pat.id,
                "name": pat.name,
                "scopes": scopes,
                "expires_at": pat.expires_at.isoformat() if pat.expires_at else None,
            }
        ),
        201,
    )


@tokens_bp.route("/<email>/tokens/<int:token_id>", methods=["DELETE"])
@check_access(["user", "admin"])
def revoke_token(email, token_id) -> Response:
    current_user = request.ctx.current_user
    if current_user.email != email and not any(r.name == "admin" for r in current_user.roles):
        return jsonify({"message": "Forbidden"}), 403

    pat = (
        db.session.query(PersonalAccessToken)
        .join(User, User.id == PersonalAccessToken.user_id)
        .filter(User.email == email, PersonalAccessToken.id == token_id, PersonalAccessToken.revoked_at.is_(None))
        .first()
    )
    if not pat:
        return jsonify({"message": "Token not found"}), 404
    pat.revoked_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "revoked"})
