import os
from flask import Blueprint, current_app, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
import requests
import json

from src.quads.web.controller.quads_api_wrapper import QuadsApiWrapper

auth_bp = Blueprint("auth", __name__)
GOOGLE_DISCOVERY_URL = os.getenv("GOOGLE_DISCOVERY_URL")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
ALLOWED_DOMAIN = "redhat.com"


@auth_bp.route("/login/", methods=["GET", "POST"])
async def login():
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    authorization_endpoint = google_provider_cfg["authorization_endpoint"]
    request_uri = current_app.client.prepare_request_uri(
        authorization_endpoint,
        redirect_uri=request.base_url + "callback",
        scope=["openid", "email", "profile"],
    )
    return redirect(request_uri)


@auth_bp.route("/login/callback")
async def callback():
    """Login with OAuth callback function."""
    code = request.args.get("code")
    google_provider_cfg = requests.get(GOOGLE_DISCOVERY_URL).json()
    token_endpoint = google_provider_cfg["token_endpoint"]
    token_url, headers, body = current_app.client.prepare_token_request(
        token_endpoint,
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code,
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET),
    )

    current_app.client.parse_request_body_response(json.dumps(token_response.json()))

    userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
    uri, headers, body = current_app.client.add_token(userinfo_endpoint)
    userinfo_response = requests.get(uri, headers=headers, data=body)
    if not userinfo_response.get("email_verified"):
        return "User email not verified by Google.", 400

    if ALLOWED_DOMAIN and not userinfo_response["email"].endswith(f"@{ALLOWED_DOMAIN}"):
        return "Email domain not allowed.", 403

    # Upsert/fetch user via REST API
    quads_api_wrapper = QuadsApiWrapper()
    remote_user = await quads_api_wrapper.upsert_user(userinfo_response)

    login_user(remote_user)
    return redirect(url_for("wiki.index"))


@auth_bp.route("/logout/")
@login_required
async def logout():
    """Logout."""
    logout_user()
    flash("You are logged out.", "info")
    return redirect(url_for("public.home"))
