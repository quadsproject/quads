from authlib.integrations.flask_client import OAuth
from flask_login import LoginManager

oauth = OAuth()
login_manager = LoginManager()


def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        server_metadata_url=app.config.get("GOOGLE_SERVER_METADATA_URL"),
        client_kwargs={"scope": "openid email profile"},
    )


def init_login_manager(app):
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"
