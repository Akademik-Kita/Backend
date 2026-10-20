from logging.config import fileConfig

from alembic import context

from app.core.config import settings
from app.core.database import get_engine
from app.models import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table":
        return name in Base.metadata.tables
    return True


options = dict(target_metadata=Base.metadata, include_object=include_object, compare_type=True)
if context.is_offline_mode():
    context.configure(
        url=settings().database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **options,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    with get_engine().connect() as connection:
        context.configure(connection=connection, **options)
        with context.begin_transaction():
            context.run_migrations()
