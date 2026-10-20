"""A complete demo using the same account/profile schema and login as the application."""

from datetime import datetime, timedelta, timezone
from uuid import NAMESPACE_URL, uuid5

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.models import AcademicRecord, InterestAssessment, StudentProfile, Subject, User
from crud_database.security import hash_password

DEMO_EMAIL = "siswa@example.invalid"
DEMO_PASSWORD = "demo-akademikkita-123"
SUBJECT_NAMES = (
    "Matematika",
    "Bahasa Indonesia",
    "Bahasa Inggris",
    "IPA",
    "IPS",
    "Seni Budaya",
    "PJOK",
    "Prakarya",
    "PPKn",
    "Agama",
)


def demo_id(key):
    return uuid5(NAMESPACE_URL, "https://example.invalid/akademikkita-demo/" + key)


DEMO_USER_ID = demo_id("student-user")
DEMO_PROFILE_ID = demo_id("student-profile")
users = User.__table__
profiles = StudentProfile.__table__
records = AcademicRecord.__table__
assessments = InterestAssessment.__table__


def seed_demo_student(db):
    if not settings().demo_mode:
        raise RuntimeError("Akun demo hanya tersedia pada DEMO_MODE=true")
    if db.get(User, DEMO_USER_ID):
        return
    db.add(
        User(
            id=DEMO_USER_ID,
            email=DEMO_EMAIL,
            full_name="Siswa Demo",
            role="siswa",
            password_hash=hash_password(DEMO_PASSWORD),
        )
    )
    db.flush()
    db.add(
        StudentProfile(
            id=DEMO_PROFILE_ID,
            user_id=DEMO_USER_ID,
            grade=9,
            current_school_name="SMP Demo",
            domisili_kecamatan="Depok",
            latitude=-6.385,
            longitude=106.825,
            budget_max_per_bulan=900000,
            max_distance_km=25,
            preferred_ownership=["negeri", "swasta"],
            profile_completeness=100,
        )
    )
    db.flush()
    for index, name in enumerate(SUBJECT_NAMES):
        subject = db.scalar(select(Subject).where(Subject.name == name))
        if subject is None:
            subject = Subject(id=uuid5(NAMESPACE_URL, "akademikkita/subject/" + name), name=name)
            db.add(subject)
            db.flush()
        for semester in (1, 2):
            db.add(
                AcademicRecord(
                    id=demo_id(f"record-{index}-{semester}"),
                    student_profile_id=DEMO_PROFILE_ID,
                    subject_id=subject.id,
                    grade_level=9,
                    semester=semester,
                    score=80 + index % 5 + semester,
                )
            )
    db.add(
        InterestAssessment(
            id=demo_id("assessment"),
            student_profile_id=DEMO_PROFILE_ID,
            instrument_version="riasec-lite-v1",
            taken_at=datetime.now(timezone.utc),
            scores=dict(
                realistic=55,
                investigative=90,
                artistic=45,
                social=70,
                enterprising=60,
                conventional=65,
            ),
        )
    )
    db.commit()


def demo_token():
    config = settings()
    if not config.demo_mode or len(config.jwt_secret.encode()) < 32:
        raise RuntimeError("Token demo memerlukan DEMO_MODE=true dan secret minimal 32 byte")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(DEMO_USER_ID), "iat": now, "exp": now + timedelta(hours=1)},
        config.jwt_secret,
        algorithm=config.jwt_algorithm,
    )
