import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, get_engine
from app.demo import demo_token, seed_demo_student
from app.main import create_app
from app.models import OWNED_TABLES, Base
from machine_learning_recommendation_system.services.importer import import_catalog, load_catalog
from machine_learning_recommendation_system.services.student import reflected_tables

ROOT = Path(__file__).resolve().parents[1]
SECRET = "test-only-secret-key-longer-than-thirty-two-bytes"


@pytest.fixture(autouse=True)
def isolated_test_configuration(tmp_path, monkeypatch):
    if os.getenv("TEST_DATABASE_URL"):
        raise RuntimeError(
            "Database eksternal ditolak untuk tes otomatis; gunakan SQLite sementara"
        )
    monkeypatch.setenv("AKADEMIKKITA_ENV_FILE", str(tmp_path / "nonexistent-test.env"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'isolated.db'}")
    settings.cache_clear()
    get_engine.cache_clear()
    yield
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    settings.cache_clear()


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", SECRET)
    monkeypatch.setenv("RECOMMENDATION_HARD_FILTERS", "true")
    settings.cache_clear()
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine, tables=OWNED_TABLES)
    with Session(engine) as db:
        seed_demo_student(db)
        import_catalog(db, load_catalog(ROOT / "data" / "schools-demo.json"))
    yield engine
    reflected_tables.cache_clear()
    engine.dispose()
    settings.cache_clear()


@pytest.fixture
def db(engine):
    with Session(engine, expire_on_commit=False) as db:
        yield db


@pytest.fixture
def client(engine):
    app = create_app()

    def override_db():
        with Session(engine, expire_on_commit=False) as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client


@pytest.fixture
def headers():
    return {"Authorization": "Bearer " + demo_token()}


@pytest.fixture
def account_db(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'student.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("JWT_SECRET_KEY", "integration-test-secret-with-more-than-32-bytes")
    settings.cache_clear()
    get_engine.cache_clear()
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    engine = create_engine(url)

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    with Session(engine, expire_on_commit=False) as session:
        yield session
    engine.dispose()
    get_engine().dispose()
    get_engine.cache_clear()
    reflected_tables.cache_clear()
    settings.cache_clear()
