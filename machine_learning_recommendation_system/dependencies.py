from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from crud_database.security import current_user
from machine_learning_recommendation_system.services.student import load_student, row_for_user

bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> UUID | None:
    if credentials is None:
        return None
    return current_user(credentials, db).id


def get_current_user(user_id: UUID | None = Depends(get_optional_user)) -> UUID:
    if user_id is None:
        raise HTTPException(401, "Login diperlukan", headers={"WWW-Authenticate": "Bearer"})
    return user_id


def get_student(
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    student = load_student(db, user_id)
    if student is None:
        raise HTTPException(409, "Profil siswa belum tersedia; isi profil terlebih dahulu")
    return student


def get_student_id(
    user_id: UUID = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UUID:
    profile = row_for_user(db, user_id)
    if profile is None:
        raise HTTPException(409, "Profil siswa belum tersedia")
    return UUID(str(profile["id"]))
