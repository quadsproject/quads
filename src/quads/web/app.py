from flask import Flask

from quads.config import Config
from quads.web.blueprints.dynamic_content import dynamic_content_bp
from quads.web.blueprints.instack import instack_bp
from quads.web.blueprints.visual import visual_bp
from quads.web.blueprints.wiki import wiki_bp
from quads.web.controller.dynamic_nav.dynamic_menus import DynamicMenus
from quads.web.controller.dynamic_nav.dynamic_nav import DynamicNav
from quads.web.controller.dynamic_nav.markup_elements import View, Navbar

WEB_CONTENT_PATH = Config.get("web_content_path")
EXCLUDE_DIRS = Config.get("web_exclude_dirs")


def initiate_navbar(flask_app):
    """
    This method initiates navbar
    """
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
            *dynamic_menus.get_dynamic_navbar_menus(),
        ),
    )
    navbar.init_app(flask_app)


def create_app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.url_map.strict_slashes = False
    flask_app.secret_key = "flask rocks!"
    flask_app.port = 5001
    flask_app.host = "0.0.0.0"
    flask_app.register_blueprint(dynamic_content_bp)
    flask_app.register_blueprint(visual_bp, url_prefix="/visual")
    flask_app.register_blueprint(instack_bp, url_prefix="/instack")
    flask_app.register_blueprint(wiki_bp)
    initiate_navbar(flask_app)

    return flask_app
