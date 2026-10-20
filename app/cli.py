import argparse
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_engine
from app.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_student
from app.models import Base, Institution, Program, Subject
from machine_learning_recommendation_system.services.importer import import_catalog, load_catalog

ROOT = Path(__file__).resolve().parents[1]


def migrate():
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")


def main():
    parser = argparse.ArgumentParser(description="AkademikKita backend")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="Buat/perbarui seluruh skema backend")
    sub.add_parser("db-check", help="Cek koneksi, migrasi, jumlah katalog, dan RLS")
    sub.add_parser("demo-init", help="Siapkan demo lengkap pada SQLite lokal")
    for name in ("validate", "import"):
        sub.add_parser(name).add_argument("path")
    args = parser.parse_args()
    try:
        if args.command == "migrate":
            migrate()
        elif args.command in ("validate", "import"):
            catalog = load_catalog(args.path)
            if args.command == "validate":
                print(f"Valid: {len(catalog.schools)} sekolah")
            else:
                if not settings().demo_mode and any(
                    "sintetis" in school.data_source.lower() for school in catalog.schools
                ):
                    raise ValueError("Gunakan database demo lokal untuk katalog sintetis")
                with Session(get_engine()) as db:
                    print(import_catalog(db, catalog))
        elif args.command == "demo-init":
            if not settings().demo_mode or get_engine().dialect.name != "sqlite":
                raise ValueError("Demo memerlukan DEMO_MODE=true dan SQLite lokal terpisah")
            migrate()
            with Session(get_engine()) as db:
                seed_demo_student(db)
                print(import_catalog(db, load_catalog(ROOT / "data/schools-demo.json")))
            print(f"Login demo: {DEMO_EMAIL}; password: {DEMO_PASSWORD}")
        else:
            engine = get_engine()
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                available = set(inspect(connection).get_table_names())
                print("Database terhubung:", engine.dialect.name)
                print(
                    "Tabel backend:",
                    len(available & set(Base.metadata.tables)),
                    "/",
                    len(Base.metadata.tables),
                )
                for model in (Subject, Institution, Program):
                    if model.__tablename__ in available:
                        print(
                            model.__tablename__ + ":",
                            connection.scalar(select(func.count()).select_from(model)),
                        )
                if engine.dialect.name == "postgresql":
                    rows = connection.execute(
                        text(
                            "SELECT c.relname,c.relrowsecurity FROM pg_class c "
                            "JOIN pg_namespace n ON n.oid=c.relnamespace "
                            "WHERE n.nspname=current_schema()"
                        )
                    ).all()
                    protected = [rls for name, rls in rows if name in Base.metadata.tables]
                    print("RLS:", sum(protected), "/", len(Base.metadata.tables))
                if "alembic_version" in available:
                    print(
                        "Migrasi:",
                        connection.scalar(text("SELECT version_num FROM alembic_version")),
                    )
    except Exception as error:
        if isinstance(error, (ValueError, RuntimeError)):
            parser.exit(1, f"Operasi gagal: {error}\n")
        parser.exit(1, f"Operasi gagal ({type(error).__name__}); periksa konfigurasi/database.\n")


if __name__ == "__main__":
    main()
