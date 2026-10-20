from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select, text

from app.core.config import settings
from app.core.database import get_engine
from app.models import Base, Subject
from tests.conftest import ROOT


def test_unified_upgrade_check_downgrade_and_seed(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'migration.db'}")
    settings.cache_clear()
    get_engine.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = get_engine()
    assert set(Base.metadata.tables) <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        names = connection.execute(select(Subject.name)).scalars().all()
    assert len(names) == 10 and "Matematika" in names
    command.check(config)
    command.downgrade(config, "base")
    assert not set(Base.metadata.tables) & set(inspect(engine).get_table_names())
    command.upgrade(config, "head")
    engine.dispose()
    get_engine.cache_clear()
    settings.cache_clear()


def test_adopt_existing_schema_preserves_subjects_and_account(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'existing.db'}")
    settings.cache_clear()
    get_engine.cache_clear()
    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")
    engine = get_engine()
    with engine.begin() as connection:
        before = connection.execute(select(Subject.id, Subject.name)).all()
        connection.execute(text("DROP TABLE alembic_version"))
        connection.execute(
            text("CREATE TABLE alembic_version_person1 (version_num varchar(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version_person1 VALUES ('p1_0001')"))
        connection.execute(
            text("CREATE TABLE alembic_version_person2 (version_num varchar(32) PRIMARY KEY)")
        )
        connection.execute(text("INSERT INTO alembic_version_person2 VALUES ('p2_0002')"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert connection.execute(select(Subject.id, Subject.name)).all() == before
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "20261014_01"
    command.check(config)
    engine.dispose()
    get_engine.cache_clear()
    settings.cache_clear()
