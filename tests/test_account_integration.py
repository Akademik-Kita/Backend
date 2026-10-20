"""Alur akun siswa sampai adapter rekomendasi pada satu database sementara."""

from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from app.models import AcademicRecord, StudentProfile, Subject, User
from app.schemas import AcademicIn, AssessmentIn, LoginIn, ProfileIn, RegisterIn
from crud_database.routers.auth import login, register
from crud_database.routers.profile import (
    add_academic,
    add_assessment,
    delete_academic,
    get_profile,
    update_profile,
)
from crud_database.security import verify_password
from machine_learning_recommendation_system.dependencies import get_optional_user
from machine_learning_recommendation_system.services.student import load_student


def test_auth_profile_and_recommendation_adapter(account_db):
    db = account_db
    body = RegisterIn(
        email=" Student@Example.com ",
        password="secret-pass-123",
        full_name="Siswa Satu",
        role="siswa",
    )
    result = register(body, db)
    user_id = UUID(result["data"]["id"])
    assert result["data"]["email"] == "student@example.com"
    user = db.get(User, user_id)
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("secret-pass-123", user.password_hash)
    assert not verify_password("salah", user.password_hash)
    token = login(LoginIn(email=user.email, password="secret-pass-123"), db)["data"]["access_token"]
    assert (
        get_optional_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db)
        == user.id
    )
    assert len(db.scalars(select(Subject)).all()) == 10

    profile = get_profile(user, db)["data"]
    assert profile["profile_completeness"] == 0
    update_profile(
        ProfileIn(
            current_school_name="SMP A",
            grade=9,
            domisili_kecamatan="Depok",
            latitude=-6.385,
            longitude=106.825,
            budget_max_per_bulan=900000,
            max_distance_km=25,
            preferred_ownership=["negeri", "swasta"],
        ),
        user,
        db,
    )
    subject = db.scalar(select(Subject).where(Subject.name == "IPA"))
    rec = add_academic(
        AcademicIn(subject_id=subject.id, grade_level=9, semester=2, score=85), user, db
    )["data"]
    assert rec["subject_name"] == "IPA"
    add_assessment(
        AssessmentIn(
            instrument_version="riasec-lite-v1",
            scores={
                "realistic": 55,
                "investigative": 90,
                "artistic": 45,
                "social": 70,
                "enterprising": 60,
                "conventional": 65,
            },
        ),
        user,
        db,
    )
    assert get_profile(user, db)["data"]["profile_completeness"] == 100
    student = load_student(db, user.id)
    assert student.academic_average == 85
    assert student.subject_count == 1
    assert student.interest_scores.investigative == 90
    assert student.preferred_ownership == ["negeri", "swasta"]

    other = register(
        RegisterIn(
            email="other@example.com",
            password="secret-pass-123",
            full_name="Siswa Dua",
            role="siswa",
        ),
        db,
    )
    other_user = db.get(User, UUID(other["data"]["id"]))
    with pytest.raises(HTTPException) as incomplete:
        load_student(db, other_user.id)
    assert incomplete.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        delete_academic(rec["id"], other_user, db)
    assert error.value.status_code == 404
    assert db.get(AcademicRecord, rec["id"]) is not None
    delete_academic(rec["id"], user, db)
    assert get_profile(user, db)["data"]["profile_completeness"] < 100
    assert db.get(StudentProfile, profile["id"]).user_id == user.id


def test_duplicate_and_invalid_profile(account_db):
    db = account_db
    body = RegisterIn(
        email="test@example.com", password="secret-pass-123", full_name="Nama", role="siswa"
    )
    register(body, db)
    with pytest.raises(HTTPException) as error:
        register(body, db)
    assert error.value.status_code == 409
    assert ProfileIn(latitude=-6.2).latitude == -6.2
    with pytest.raises(ValueError):
        ProfileIn(preferred_ownership=["negeri", "negeri"])
