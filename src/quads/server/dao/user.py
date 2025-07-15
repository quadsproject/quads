import logging
from typing import List, Optional

from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash

from quads.server.dao.baseDao import BaseDao
from quads.server.models import Role, RolesUsers, User, db


class UserDao(BaseDao):
    """
    User data access object for database operations on User model.
    """

    @staticmethod
    def get_user(email: str) -> Optional[User]:
        """
        Get user by email address.

        :param email: User email address
        :return: User object or None
        """
        return db.session.query(User).filter(User.email == email).first()

    @staticmethod
    def get_users() -> List[User]:
        """
        Get all users.

        :return: List of User objects
        """
        return db.session.query(User).all()

    @staticmethod
    def create_user(email: str, password: str, roles: List[Role] = None, active: bool = True) -> User:
        """
        Create a new user.

        :param email: User email address
        :param password: User password (plaintext)
        :param roles: List of Role objects
        :param active: User active status
        :return: Created User object
        :raises IntegrityError: If user already exists
        """
        try:
            user = User(email=email, active=active, fs_uniquifier=email)  # Using email as uniquifier for simplicity
            user.password = password  # This will be hashed by the model

            if roles:
                user.roles = roles

            db.session.add(user)
            db.session.commit()

            logging.info(f"User created: {email}")
            return user

        except IntegrityError:
            db.session.rollback()
            raise IntegrityError(f"User with email {email} already exists", None, None)

    @staticmethod
    def update_user(email: str, **kwargs) -> Optional[User]:
        """
        Update user attributes.

        :param email: User email address
        :param kwargs: Attributes to update
        :return: Updated User object or None
        """
        user = UserDao.get_user(email)
        if not user:
            return None

        for key, value in kwargs.items():
            if key == "password":
                user.password = value  # This will be hashed by the model
            elif key == "new_email":
                user.email = value
            elif hasattr(user, key):
                setattr(user, key, value)

        db.session.commit()
        logging.info(f"User updated: {email}")
        return user

    @staticmethod
    def delete_user(email: str) -> bool:
        """
        Delete a user and their role associations.

        :param email: User email address
        :return: True if user was deleted, False if user not found
        """
        user = UserDao.get_user(email)
        if not user:
            return False

        # Remove user role associations
        db.session.query(RolesUsers).filter(RolesUsers.user_id == user.id).delete()

        # Delete the user
        db.session.delete(user)
        db.session.commit()

        logging.info(f"User deleted: {email}")
        return True

    @staticmethod
    def change_user_password(email: str, new_password: str) -> bool:
        """
        Change user password.

        :param email: User email address
        :param new_password: New password (plaintext)
        :return: True if password was changed, False if user not found
        """
        user = UserDao.get_user(email)
        if not user:
            return False

        user.password = new_password  # This will be hashed by the model
        db.session.commit()

        logging.info(f"Password changed for user: {email}")
        return True

    @staticmethod
    def set_user_active(email: str, active: bool) -> bool:
        """
        Set user active status.

        :param email: User email address
        :param active: Active status
        :return: True if status was changed, False if user not found
        """
        user = UserDao.get_user(email)
        if not user:
            return False

        user.active = active
        db.session.commit()

        logging.info(f"User active status changed to {active}: {email}")
        return True

    @staticmethod
    def change_user_email(old_email: str, new_email: str) -> bool:
        """
        Change user email address.

        :param old_email: Current email address
        :param new_email: New email address
        :return: True if email was changed, False if user not found
        :raises IntegrityError: If new email already exists
        """
        user = UserDao.get_user(old_email)
        if not user:
            return False

        # Check if new email already exists
        existing_user = UserDao.get_user(new_email)
        if existing_user:
            raise IntegrityError(f"User with email {new_email} already exists", None, None)

        user.email = new_email
        db.session.commit()

        logging.info(f"User email changed from {old_email} to {new_email}")
        return True
