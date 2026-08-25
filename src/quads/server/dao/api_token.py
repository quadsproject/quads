from datetime import datetime

from quads.server.dao.baseDao import BaseDao, EntryNotFound, InvalidArgument
from quads.server.models import ApiToken, User, db


class ApiTokenDao(BaseDao):
    @classmethod
    def create_token(cls, user_id, name):
        existing = db.session.query(ApiToken).filter(ApiToken.user_id == user_id, ApiToken.name == name).first()
        if existing:
            raise InvalidArgument(f"Token with name '{name}' already exists")

        raw_token, token_hash, token_prefix = ApiToken.generate_token()
        token = ApiToken(
            name=name,
            token_hash=token_hash,
            token_prefix=token_prefix,
            user_id=user_id,
        )
        db.session.add(token)
        cls.safe_commit()
        return token, raw_token

    @classmethod
    def get_tokens_by_user(cls, user_id):
        return (
            db.session.query(ApiToken).filter(ApiToken.user_id == user_id).order_by(ApiToken.created_at.desc()).all()
        )

    @classmethod
    def get_token_by_id(cls, token_id, user_id):
        return db.session.query(ApiToken).filter(ApiToken.id == token_id, ApiToken.user_id == user_id).first()

    @classmethod
    def delete_token(cls, token_id, user_id):
        token = cls.get_token_by_id(token_id, user_id)
        if not token:
            raise EntryNotFound(f"Token not found: {token_id}")
        db.session.delete(token)
        cls.safe_commit()

    @classmethod
    def authenticate_token(cls, raw_token):
        token_hash = ApiToken.hash_token(raw_token)
        token = db.session.query(ApiToken).filter(ApiToken.token_hash == token_hash).first()
        if not token:
            return None
        token.last_used = datetime.now()
        cls.safe_commit()
        return db.session.query(User).filter(User.id == token.user_id).first()
