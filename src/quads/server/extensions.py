# -*- coding: utf-8 -*-
"""Extensions module. Each extension is initialized in the app factory located in app.py."""

from flask_httpauth import HTTPBasicAuth
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_security import Security

login_manager = LoginManager()
migrate = Migrate()
security = Security()
basic_auth = HTTPBasicAuth()
