import os


class BaseConfig(object):
    JOB_INDEX_PER_PAGE = 18
    COMPANY_INDEX_PER_PAGE = 20
    COMPANY_DETAIL_PER_PAGE = 10
    LIST_PER_PAGE = 15
    API_VERSION = "v3"


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://postgres:postgres@quads_db:5432/quads",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://postgres:postgres@localhost:5432/quads",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = True


class TestingConfig(BaseConfig):
    DEBUG = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI",
        "postgresql://postgres:postgres@quads_db:5432/quads",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TESTING = True


configs = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
