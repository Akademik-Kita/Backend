from functools import lru_cache

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


@lru_cache
def get_engine():
    url = settings().database_url
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["connect_args"] = {"connect_timeout": 5}
        # Jangan membuka puluhan koneksi PostgreSQL melalui pooler per proses.
        kwargs.update(pool_size=3, max_overflow=2, pool_timeout=10, pool_recycle=1800)
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def enable_fk(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

    return engine


def get_db():
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise
