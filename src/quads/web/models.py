from flask_login import UserMixin


class WebUser(UserMixin):
    def __init__(
        self, email, google_id=None, profile_picture=None, active=True, last_login=None, roles=None, ssh_key=None
    ):
        self.email = email
        self.google_id = google_id
        self.profile_picture = profile_picture
        self.active = active
        self.last_login = last_login
        self.roles = roles or []
        self.ssh_key = ssh_key

    def get_id(self):
        return self.email

    @property
    def is_active(self):
        return self.active

    @classmethod
    def from_dict(cls, data):
        if not data:
            return None
        return cls(
            email=data.get("email"),
            google_id=data.get("google_id"),
            profile_picture=data.get("profile_picture"),
            active=data.get("active", True),
            last_login=data.get("last_login"),
            roles=data.get("roles", []),
            ssh_key=data.get("ssh_key"),
        )
