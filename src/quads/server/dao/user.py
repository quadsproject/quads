import uuid

from quads.server.dao.baseDao import BaseDao, EntryNotFound
from quads.server.models import Role, User, db


class UserDao(BaseDao):
    @classmethod
    def get_user_by_email(cls, email):
        return db.session.query(User).filter(User.email == email).first()

    @classmethod
    def get_user_by_google_id(cls, google_id):
        return db.session.query(User).filter(User.google_id == google_id).first()

    @classmethod
    def create_user(cls, email, google_id=None, profile_picture=None, active=True, fs_uniquifier=None):
        user = User(
            email=email,
            google_id=google_id,
            profile_picture=profile_picture,
            active=active,
            fs_uniquifier=fs_uniquifier or str(uuid.uuid4()),
        )
        user_role = db.session.query(Role).filter(Role.name == "user").first()
        if user_role:
            user.roles.append(user_role)

        db.session.add(user)
        cls.safe_commit()
        return user

    @classmethod
    def update_user(cls, email, **kwargs):
        user = cls.get_user_by_email(email)
        if not user:
            raise EntryNotFound(f"User not found: {email}")

        for key, value in kwargs.items():
            if key == "password":
                user.password = value
            elif hasattr(user, key):
                setattr(user, key, value)

        cls.safe_commit()
        return user
