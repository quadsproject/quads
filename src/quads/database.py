from quads.server.models import Base, Engine, engine_from_config


def init_db(config=None):
    # import all modules here that might define models so that
    # they will be registered properly on the metadata.  Otherwise
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
        conn.execute("COMMIT")
        conn.execute(f"CREATE DATABASE {url.database}")
        conn.close()
        tmp_engine.dispose()

    quads.server.models.Base.metadata.create_all(bind=engine)


def drop_db(config=None):
    engine = Engine
    if config:
        engine = engine_from_config(config)
    Base.metadata.drop_all(bind=engine)
