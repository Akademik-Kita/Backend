"""Create the backend or adopt the existing complete schema without rebuilding data."""

from alembic import context, op
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text

from app.models import Base
from migrations.legacy import account, catalog, protection

revision = "20261014_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if not context.is_offline_mode():
        existing = set(inspect(connection).get_table_names())
        owned = set(Base.metadata.tables)
        if existing & owned:
            if not owned <= existing:
                raise RuntimeError(
                    "Skema backend lama belum lengkap; migrasi berhenti tanpa mengubah data"
                )
            expected = {"alembic_version_person1": "p1_0001", "alembic_version_person2": "p2_0002"}
            for table, version in expected.items():
                if table not in existing or connection.execute(
                    text(f'SELECT version_num FROM "{table}"')
                ).scalars().all() != [version]:
                    raise RuntimeError(
                        "Revisi database lama belum sesuai; periksa migrasi sebelum menyatukan"
                    )
            check = MigrationContext.configure(
                connection,
                opts={
                    "include_object": lambda obj, name, type_, reflected, compare_to: (
                        type_ != "table" or name in owned
                    ),
                    "compare_type": True,
                },
            )
            if compare_metadata(check, Base.metadata):
                raise RuntimeError(
                    "Skema database berbeda dari model; penyatuan dihentikan agar data tetap aman"
                )
            protection.upgrade()
            return
    account.upgrade()
    catalog.upgrade()
    protection.upgrade()


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        raise RuntimeError("Penghapusan tabel PostgreSQL membutuhkan migrasi data terpisah")
    protection.downgrade()
    catalog.downgrade()
    account.downgrade()
