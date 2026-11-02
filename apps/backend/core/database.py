from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import get_settings


@lru_cache
def get_engine():
    url = get_settings().database_url
    return create_engine(url, pool_pre_ping=True)


def session_factory():
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_db():
    with session_factory()() as db:
        try:
            yield db
        finally:
            db.rollback()
