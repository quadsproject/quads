import os
from datetime import timedelta

from flask import Flask
from flask_login import current_user
from flask_wtf.csrf import CSRFProtect

from quads.config import Config
from quads.quads_api import QuadsApi
from quads.web.auth_helpers import get_username_from_email
from quads.web.blueprints.auth import auth_bp
from quads.web.blueprints.connectivity import connectivity_bp
from quads.web.blueprints.dynamic_content import dynamic_content_bp
from quads.web.blueprints.instack import instack_bp
from quads.web.blueprints.visual import visual_bp
from quads.web.blueprints.wiki import wiki_bp
from quads.web.controller.dynamic_nav.dynamic_menus import DynamicMenus
from quads.web.controller.dynamic_nav.dynamic_nav import DynamicNav
from quads.web.controller.dynamic_nav.markup_elements import Subgroup, View, Navbar
from quads.web.extensions import init_login_manager, init_oauth, login_manager

WEB_CONTENT_PATH = Config.get("web_content_path")
EXCLUDE_DIRS = Config.get("web_exclude_dirs")


def initiate_navbar(flask_app):
    navbar = DynamicNav()
    dynamic_menus = DynamicMenus(exclude_dir_path=EXCLUDE_DIRS, web_dir_path=WEB_CONTENT_PATH)
    navbar.register_element(
        "navbar",
        Navbar(
            "",
            View(text="Inventory", endpoint="wiki.create_inventory"),
            View(text="Assignments", endpoint="wiki.index"),
            View(text="Vlans", endpoint="wiki.create_vlans"),
            View(text="Available", endpoint="wiki.available"),
            View(text="Connectivity", endpoint="connectivity.index"),
            Subgroup(
                "Visuals",
                View(text="Current Month", endpoint="visual.visuals", **{"when": "current"}),
                View(text="Next Month", endpoint="visual.visuals", **{"when": "next"}),
                View(text="All Time", endpoint="visual.index"),
            ),
            *dynamic_menus.get_dynamic_navbar_menus(),
        ),
    )
    navbar.init_app(flask_app)


def set_global_variables(flask_app):
    lab_name = Config.get("lab_name")
    flask_app.add_template_global(lab_name, name="lab_name")


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.url_map.strict_slashes = False
    google_oauth_conf = Config.get("google_oauth", {})
    oauth_settings = Config.get("oauth_settings", {})

    secret_key = oauth_settings.get("flask_secret_key")
    if not secret_key:
        raise RuntimeError("flask_secret_key must be set in conf/oauth.yml")
    flask_app.secret_key = secret_key
    flask_app.port = 5001
    flask_app.host = "0.0.0.0"

    flask_app.config["GOOGLE_CLIENT_ID"] = google_oauth_conf.get("client_id")
    flask_app.config["GOOGLE_CLIENT_SECRET"] = google_oauth_conf.get("client_secret")
    flask_app.config["GOOGLE_SERVER_METADATA_URL"] = google_oauth_conf.get(
        "server_metadata_url",
        "https://accounts.google.com/.well-known/openid-configuration",
    )
    flask_app.config["SESSION_COOKIE_HTTPONLY"] = True
    flask_app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=oauth_settings.get("session_lifetime_hours", 24))
    flask_app.config["REMEMBER_COOKIE_DURATION"] = timedelta(days=oauth_settings.get("remember_me_duration_days", 30))
    flask_app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    flask_app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"
    flask_app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"
    flask_app.config["REMEMBER_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") != "development"

    CSRFProtect(flask_app)

    init_oauth(flask_app)
    init_login_manager(flask_app)

    quads_api = QuadsApi(Config)

    @login_manager.user_loader
    def load_user(user_email):
        return quads_api.get_user(email=user_email)

    @flask_app.context_processor
    def inject_user():
        return {
            "current_user": current_user,
            "username": get_username_from_email(current_user.email) if current_user.is_authenticated else None,
        }

    flask_app.register_blueprint(auth_bp, url_prefix="/auth")
    flask_app.register_blueprint(dynamic_content_bp)
    flask_app.register_blueprint(visual_bp, url_prefix="/visual")
    flask_app.register_blueprint(instack_bp, url_prefix="/instack")
    flask_app.register_blueprint(wiki_bp)
    flask_app.register_blueprint(connectivity_bp, url_prefix="/connectivity")
    initiate_navbar(flask_app)
    set_global_variables(flask_app)

    return flask_app
