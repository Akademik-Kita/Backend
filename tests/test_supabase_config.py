import pytest
from sqlalchemy.engine import make_url

from app.core.config import database_url


def test_session_pooler_uri_uses_psycopg_and_tls_without_changing_password():
    raw = "postgresql://postgres.ref:pass%40word@aws-0-region.pooler.supabase.com:5432/postgres"
    parsed = make_url(database_url(raw))
    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.password == "pass@word"
    assert parsed.query["sslmode"] == "require"
    assert parsed.username == "postgres.ref"


def test_direct_connection_and_custom_verify_full():
    parsed = make_url(
        database_url(
            "postgres://postgres:secret@db.ref.supabase.co:5432/postgres?sslmode=verify-full&sslrootcert=C%3A%5Cca.crt"
        )
    )
    assert parsed.drivername == "postgresql+psycopg"
    assert parsed.query["sslmode"] == "verify-full"
    assert parsed.query["sslrootcert"] == r"C:\ca.crt"


@pytest.mark.parametrize(
    "raw",
    [
        "postgresql://postgres.ref:secret@aws-0-region.pooler.supabase.com:6543/postgres",
        "postgresql://postgres.ref:secret@aws-0-region.pooler.supabase.com:5432/postgres?sslmode=disable",
        "postgresql://postgres.ref:YOUR-PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres",
        "mysql://user:secret@host/db",
    ],
)
def test_unsafe_or_unsupported_uri_rejected(raw):
    with pytest.raises(ValueError):
        database_url(raw)


def test_local_sqlite_demo_still_supported():
    assert database_url("sqlite:///./akademikkita-demo.db") == "sqlite:///./akademikkita-demo.db"
