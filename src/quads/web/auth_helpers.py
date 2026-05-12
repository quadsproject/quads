import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from quads.config import Config
from quads.server.models import User, Role, db

ALLOWED_PICTURE_DOMAINS = {
    "lh3.googleusercontent.com",
    "lh4.googleusercontent.com",
    "lh5.googleusercontent.com",
    "lh6.googleusercontent.com",
}


def _sanitize_profile_picture(url):
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme == "https" and parsed.hostname in ALLOWED_PICTURE_DOMAINS:
            return url
    except Exception:
        pass
    return None


def get_or_create_oauth_user(user_info):
    google_id = user_info["sub"]
    email = user_info["email"]
    picture = _sanitize_profile_picture(user_info.get("picture"))

    user = User.query.filter_by(google_id=google_id).first()

    if not user:
        user = User.query.filter_by(email=email).first()

        if user:
            user.google_id = google_id
            user.profile_picture = picture
        else:
            user = User(
                email=email,
                google_id=google_id,
                profile_picture=picture,
                active=True,
                fs_uniquifier=str(uuid.uuid4()),
            )
            user_role = Role.query.filter_by(name="user").first()
            if user_role:
                user.roles.append(user_role)

            db.session.add(user)

    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    return user


def is_allowed_domain(email):
    allowed_domains = Config.get("oauth_settings", {}).get("allowed_domains", [])

    if not allowed_domains:
        return False

    parts = email.split("@")
    if len(parts) != 2:
        return False

    return parts[1] in allowed_domains


def get_username_from_email(email):
    return email.split("@")[0] if email else None
