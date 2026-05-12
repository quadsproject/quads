import logging

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from quads.web.auth_helpers import get_or_create_oauth_user, get_username_from_email, is_allowed_domain
from quads.web.extensions import oauth
from quads.config import Config
from quads.quads_api import QuadsApi
from quads.server.models import db

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

    user = get_or_create_oauth_user(user_info)
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

    return render_template(
        "auth/profile.html",
        user=current_user,
        username=username,
        assignments=user_assignments,
    )


@auth_bp.route("/profile/reset-password", methods=["POST"])
@login_required
def reset_password():
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not new_password or len(new_password) < 8:
        flash("Password must be at least 8 characters.", "danger")
        return redirect(url_for("auth.profile"))

    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("auth.profile"))

    current_user.password = new_password
    db.session.commit()

    flash("Password updated successfully. You can now use API endpoints.", "success")
    return redirect(url_for("auth.profile"))
