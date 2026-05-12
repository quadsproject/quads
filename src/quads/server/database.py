from sqlalchemy import text

from quads.server.models import Base, Engine, Role, User, db, engine_from_config


def init_db(config=None):
    # Import all modules here that might define models so that
    # they will be registered properly on the metadata. Otherwise,
    # you will have to import them first before calling init_db()
    import quads.server.models

    engine = Engine
    if config:
        engine = engine_from_config(config)

    try:
        conn = engine.connect()
        conn.close()
    except Exception:
        import sqlalchemy

        url = engine.url
        default_url = url.set(database="postgres")
        tmp_engine = sqlalchemy.create_engine(default_url)
        conn = tmp_engine.connect()
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        conn.execute(text(f"CREATE DATABASE {url.database}"))
        conn.close()
        tmp_engine.dispose()

    Base.metadata.create_all(bind=engine)


def drop_all(config=None):
    engine = Engine
    if config:
        engine = engine_from_config(config)
    Base.metadata.drop_all(bind=engine)


def populate(user_datastore):
    admin_role_name = "admin"
    admin_role_description = "Administrative role"

    user_role_name = "user"
    user_role_description = "Regular user role"

    admin_role = create_role(admin_role_name, admin_role_description)
    user_role = create_role(user_role_name, user_role_description)

    regular_user = "gonza@example.com"
    admin_user = "grafuls@example.com"

    admin_user_added = create_user(user_datastore, admin_user, "password", [admin_role])
    regular_user_added = create_user(user_datastore, regular_user, "password", [user_role])

    if admin_role or user_role or admin_user_added or regular_user_added:
        db.session.commit()


def create_user(user_datastore, email, password, roles):
    user_entry = db.session.query(User).filter(User.email == email).first()

    if not user_entry:
        user_datastore.create_user(email=email, password=password, roles=roles)
        return True
    return False


def modify_user(user_datastore, email, new_password=None):
    user = user_datastore.find_user(email=email)
    if not user:
        return False

    if new_password:
        user_datastore.set_password(user, new_password)
        return True
    return False


def remove_user(user_datastore, email):
    user = user_datastore.find_user(email=email)

    if user:
        user_datastore.delete_user(user)
        return True
    return False


def create_role(name, description):
    role_entry = db.session.query(Role).filter(Role.name == name).first()
    if not role_entry:
        role = Role(name=name, description=description)
        db.session.add(role)
        return role
    return role_entry
