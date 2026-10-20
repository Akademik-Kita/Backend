import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def database_url(value: str) -> str:
    """Terima URI dashboard Supabase dan gunakan driver Psycopg 3 dengan TLS."""
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    url = make_url(value)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername not in {"postgresql+psycopg", "sqlite"}:
        raise ValueError(
            "DATABASE_URL harus memakai PostgreSQL/Psycopg atau SQLite untuk demo lokal"
        )
    host = (url.host or "").lower()
    if host.endswith((".supabase.com", ".supabase.co")):
        if url.port == 6543:
            raise ValueError(
                "Gunakan Session pooler port 5432 untuk aplikasi ini, bukan Transaction pooler 6543"
            )
        if (
            not url.username
            or not url.password
            or "YOUR-PASSWORD" in url.password
            or "PASSWORD" in url.password
        ):
            raise ValueError("Lengkapi username dan password database Supabase di .env")
        mode = url.query.get("sslmode")
        if mode and mode not in {"require", "verify-ca", "verify-full"}:
            raise ValueError(
                "Koneksi Supabase wajib memakai sslmode=require atau verifikasi sertifikat"
            )
        if not mode:
            url = url.update_query_dict({"sslmode": "require"})
    return url.render_as_string(hide_password=False)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name, str(default)).lower()
    if value not in {"true", "false"}:
        raise RuntimeError(f"{name} harus true atau false")
    return value == "true"


class Settings:
    def __init__(self):
        env_file = (
            os.getenv("AKADEMIKKITA_ENV_FILE") or Path(__file__).resolve().parents[2] / ".env"
        )
        load_dotenv(env_file)
        self.database_url = database_url(
            os.getenv("DATABASE_URL", "sqlite:///./akademikkita-demo.db")
        )
        self.demo_mode = env_bool("DEMO_MODE", False)
        self.hard_filters = env_bool("RECOMMENDATION_HARD_FILTERS", False)
        self.jwt_secret = os.getenv("JWT_SECRET_KEY", "")
        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        if self.jwt_algorithm != "HS256":
            raise RuntimeError(
                "Verifier bawaan mendukung HS256; gunakan adapter auth akun dan profil untuk algoritma lain"
            )
        self.cors_origins = [
            x.strip()
            for x in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if x.strip()
        ]


@lru_cache
def settings() -> Settings:
    return Settings()
