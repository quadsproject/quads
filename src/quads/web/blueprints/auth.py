import logging
import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from quads.web.auth_helpers import get_or_create_oauth_user, get_username_from_email, is_allowed_domain
from quads.web.extensions import oauth
from quads.config import Config
from quads.quads_api import QuadsApi

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("wiki.index"))
    redirect_uri = url_for("auth.callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@auth_bp.route("/callback")
def callback():
    token = oauth.google.authorize_access_token()
    user_info = token.get("userinfo")
    if not user_info:
        user_info = oauth.google.userinfo()

    if not user_info.get("email_verified"):
        flash("Email not verified by Google.", "danger")
        return redirect(url_for("wiki.index"))

    email = user_info["email"]
    if not is_allowed_domain(email):
        flash("Access denied. Please use an authorized email domain.", "danger")
        return redirect(url_for("wiki.index"))

    quads = QuadsApi(Config)
    user = get_or_create_oauth_user(quads, user_info)
    login_user(user, remember=True)

    return redirect(url_for("wiki.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("wiki.index"))


@auth_bp.route("/profile")
@login_required
def profile():
    quads = QuadsApi(Config)
    username = get_username_from_email(current_user.email)

    user_assignments = []
    try:
        assignments = quads.get_active_assignments()
        for assignment in assignments:
            if assignment.owner and assignment.owner.lower() == username.lower():
                user_assignments.append(assignment)
    except Exception:
        logger.exception("Failed to fetch assignments for profile")

    api_tokens = []
    try:
        api_tokens = quads.get_api_tokens(current_user.email)
    except Exception:
        logger.exception("Failed to fetch API tokens for profile")

    ssh_key = None
    release_command = None
    try:
        user_data = quads.get_user(email=current_user.email)
        if user_data:
            ssh_key = getattr(user_data, "ssh_key", None)
            release_command = getattr(user_data, "release_command", None)
    except Exception:
        logger.exception("Failed to fetch user data for profile")

    new_token = session.pop("new_token", None)
    new_token_name = session.pop("new_token_name", None)

    return render_template(
        "auth/profile.html",
        user=current_user,
        username=username,
        assignments=user_assignments,
        api_tokens=api_tokens,
        ssh_key=ssh_key,
        release_command=release_command,
        new_token=new_token,
        new_token_name=new_token_name,
    )


@auth_bp.route("/profile/tokens", methods=["POST"])
@login_required
def create_token():
    token_name = request.form.get("token_name", "").strip()
    if not token_name:
        flash("Token name is required.", "danger")
        return redirect(url_for("auth.profile"))
    if len(token_name) > 256:
        flash("Token name must be 256 characters or fewer.", "danger")
        return redirect(url_for("auth.profile"))

    quads = QuadsApi(Config)
    try:
        result = quads.create_api_token(current_user.email, token_name)
        raw_token = result.get("token")
        if raw_token:
            session["new_token"] = raw_token
            session["new_token_name"] = token_name
            flash("Token created. Copy it now — it will not be shown again!", "success")
        else:
            flash("Token created but could not retrieve the value.", "warning")
    except Exception:
        logger.exception("Failed to create API token")
        flash("Failed to create token.", "danger")

    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/tokens/<int:token_id>/delete", methods=["POST"])
@login_required
def delete_token(token_id):
    quads = QuadsApi(Config)
    try:
        quads.delete_api_token(current_user.email, token_id)
        flash("Token revoked.", "success")
    except Exception:
        logger.exception("Failed to revoke API token")
        flash("Failed to revoke token.", "danger")

    return redirect(url_for("auth.profile"))


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


@auth_bp.route("/profile/ssh-key", methods=["POST"])
@login_required
def update_ssh_key():
    ssh_key = request.form.get("ssh_key", "").strip()

    if ssh_key:
        if not ssh_key.startswith(VALID_SSH_KEY_PREFIXES):
            flash("Invalid SSH key format. Key must start with a valid type (e.g. ssh-ed25519, ssh-rsa).", "danger")
            return redirect(url_for("auth.profile"))
        parts = ssh_key.split()
        if len(parts) < 2:
            flash("Invalid SSH key format. Expected: type base64 [comment]", "danger")
            return redirect(url_for("auth.profile"))

    quads = QuadsApi(Config)
    try:
        quads.update_ssh_key(current_user.email, ssh_key or None)
        if ssh_key:
            flash("SSH key saved.", "success")
        else:
            flash("SSH key removed.", "success")
    except Exception:
        logger.exception("Failed to update SSH key")
        flash("Failed to update SSH key.", "danger")

    return redirect(url_for("auth.profile"))


@auth_bp.route("/profile/release-command", methods=["POST"])
@login_required
def update_release_command():
    command = request.form.get("release_command", "").strip()

    if command:
        if len(command) > 1024:
            flash("Command exceeds 1024 character limit.", "danger")
            return redirect(url_for("auth.profile"))
        cleaned = re.sub(r"[^\x09\x0a\x0d\x20-\x7e]", "", command)
        if cleaned != command:
            flash("Command contains invalid control characters.", "danger")
            return redirect(url_for("auth.profile"))

    quads = QuadsApi(Config)
    try:
        quads.update_user(current_user.email, {"release_command": command or None})
        if command:
            flash("Release command saved.", "success")
        else:
            flash("Release command removed.", "success")
    except Exception:
        logger.exception("Failed to update release command")
        flash("Failed to update release command.", "danger")

    return redirect(url_for("auth.profile"))
