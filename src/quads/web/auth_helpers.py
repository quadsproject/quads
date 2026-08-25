from datetime import datetime, timezone
from urllib.parse import urlparse

from quads.config import Config

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


def get_or_create_oauth_user(quads_api, user_info):
    google_id = user_info["sub"]
    email = user_info["email"]
    picture = _sanitize_profile_picture(user_info.get("picture"))

    user = quads_api.get_user(google_id=google_id)

    if not user:
        user = quads_api.get_user(email=email)

        if user:
            quads_api.update_user(email, {"google_id": google_id, "profile_picture": picture})
        else:
            user = quads_api.create_user(
                {
                    "email": email,
                    "google_id": google_id,
                    "profile_picture": picture,
                    "active": True,
                }
            )

    quads_api.update_user(email, {"last_login": datetime.now(timezone.utc).isoformat()})

    return quads_api.get_user(email=email)


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


def is_cloud_owner(username, owner, ccuser, roles=None) -> bool:
    if roles and "admin" in roles:
        return True
    if not username:
        return False
    username = username.lower()
    if owner and owner.lower() == username:
        return True
    for entry in ccuser or []:
        if not isinstance(entry, str):
            continue
        candidates = [entry] if "@" not in entry else [entry, entry.split("@")[0]]
        if any(c.lower() == username for c in candidates):
            return True
    return False
