import os
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def require_secret():
    secret = settings().jwt_secret
    if len(secret.encode()) < 32 or secret.startswith("GANTI_"):
        raise HTTPException(503, "Atur JWT_SECRET_KEY acak minimal 32 byte di .env")
    return secret


def hash_password(password: str):
    # PHC menyimpan salt dan parameter Argon2id bersama hash; password tidak disimpan.
    return Argon2id(
        salt=os.urandom(16), length=32, iterations=3, lanes=4, memory_cost=64 * 1024
    ).derive_phc_encoded(password.encode())


def verify_password(password: str, encoded: str):
    try:
        Argon2id.verify_phc_encoded(password.encode(), encoded)
        return True
    except (InvalidKey, ValueError):
        return False


def issue_token(user_id: UUID):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(hours=1)},
        require_secret(),
        algorithm="HS256",
    )


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Login diperlukan", headers={"WWW-Authenticate": "Bearer"})
    try:
        token = jwt.decode(
            credentials.credentials,
            require_secret(),
            algorithms=["HS256"],
            options={"require": ["sub", "exp"]},
        )
        user_id = UUID(token["sub"])
    except (jwt.InvalidTokenError, TypeError, ValueError):
        raise HTTPException(
            401, "Token tidak valid atau kedaluwarsa", headers={"WWW-Authenticate": "Bearer"}
        ) from None
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Akun tidak ditemukan atau tidak aktif")
    return user


def student_user(user: User = Depends(current_user)) -> User:
    if user.role != "siswa":
        raise HTTPException(403, "Profil siswa hanya tersedia untuk akun siswa")
    return user
