from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import StudentProfile, User
from app.schemas import Envelope, LoginIn, LoginOut, RegisterIn, UserOut, envelope
from crud_database.security import (
    current_user,
    hash_password,
    issue_token,
    require_secret,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", status_code=201, response_model=Envelope[UserOut])
def register(body: RegisterIn, db: Session = Depends(get_db)):
    require_secret()
    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(409, "Email sudah terdaftar")
    user = User(
        email=body.email,
        full_name=body.full_name,
        role=body.role,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.flush()
        if body.role == "siswa":
            db.add(StudentProfile(user_id=user.id, profile_completeness=0))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email sudah terdaftar") from None
    return envelope(UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"))


@router.post("/login", response_model=Envelope[LoginOut])
def login(body: LoginIn, db: Session = Depends(get_db)):
    require_secret()
    user = db.scalar(select(User).where(User.email == body.email.strip().lower()))
    if user is None or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Email atau password salah")
    return envelope(
        {
            "access_token": issue_token(user.id),
            "token_type": "bearer",
            "user": UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"),
        }
    )


@router.get("/me", response_model=Envelope[UserOut])
def me(user: User = Depends(current_user)):
    return envelope(UserOut.model_validate(user, from_attributes=True).model_dump(mode="json"))
