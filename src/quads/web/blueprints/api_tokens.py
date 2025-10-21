from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from quads.web.controller.quads_api_wrapper import QuadsApiWrapper

api_tokens_bp = Blueprint("api_tokens", __name__, template_folder="templates")


@api_tokens_bp.route("/", methods=["GET"])
@login_required
def tokens_index():
    api = QuadsApiWrapper().quads_api
    resp = api.list_tokens(current_user.email)
    tokens = resp.json() if resp.status_code == 200 else []
    return render_template("account/tokens.html", tokens=tokens)


@api_tokens_bp.route("/", methods=["POST"])
@login_required
def tokens_create():
    name = request.form.get("name") or "api-token"
    scopes = request.form.getlist("scopes")
    expires_in_days = int(request.form.get("expires_in_days") or 0)
    api = QuadsApiWrapper().quads_api
    resp = api.create_token(current_user.email, name, scopes, expires_in_days)
    if resp.status_code == 201:
        token_plaintext = resp.json()["token"]
        flash(f"Copy your token now: {token_plaintext}", "success")
    else:
        flash("Failed to create token", "danger")
    return redirect(url_for("api_tokens.tokens_index"))


@api_tokens_bp.route("/<int:token_id>/revoke", methods=["POST"])
@login_required
def tokens_revoke(token_id):
    api = QuadsApiWrapper().quads_api
    api.revoke_token(current_user.email, token_id)
    flash("Token revoked", "info")
    return redirect(url_for("api_tokens.tokens_index"))
