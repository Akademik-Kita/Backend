from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import (
    AcademicRecord,
    Achievement,
    InterestAssessment,
    StudentProfile,
    Subject,
    User,
)
from app.schemas import (
    AcademicIn,
    AcademicOut,
    AcademicScoreIn,
    AchievementIn,
    AchievementOut,
    AssessmentIn,
    AssessmentOut,
    DeletedOut,
    Envelope,
    ProfileIn,
    ProfileOut,
    SubjectOut,
    envelope,
)
from crud_database.security import student_user

router = APIRouter(prefix="/profile", tags=["Profil siswa"])


def profile_for(db: Session, user: User) -> StudentProfile:
    profile = db.scalar(select(StudentProfile).where(StudentProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(409, "Profil siswa belum tersedia")
    return profile


def completeness(db, profile):
    # Sembilan kelompok data; lokasi dihitung lengkap hanya jika kedua koordinat ada.
    present = [
        bool(profile.current_school_name),
        profile.grade is not None,
        bool(profile.domisili_kecamatan),
        profile.latitude is not None and profile.longitude is not None,
        profile.budget_max_per_bulan is not None,
        profile.max_distance_km is not None,
        bool(profile.preferred_ownership),
        db.scalar(
            select(func.count())
            .select_from(AcademicRecord)
            .where(AcademicRecord.student_profile_id == profile.id)
        )
        > 0,
        db.scalar(
            select(func.count())
            .select_from(InterestAssessment)
            .where(InterestAssessment.student_profile_id == profile.id)
        )
        > 0,
    ]
    return round(100 * sum(present) / len(present))


def refresh_completeness(db, profile):
    db.flush()
    profile.profile_completeness = completeness(db, profile)
    db.commit()


def profile_data(profile):
    return {
        key: getattr(profile, key)
        for key in (
            "id",
            "user_id",
            "current_school_name",
            "grade",
            "domisili_kecamatan",
            "latitude",
            "longitude",
            "budget_max_per_bulan",
            "max_distance_km",
            "preferred_ownership",
            "profile_completeness",
        )
    }


def academic_data(record, name):
    return {
        "id": record.id,
        "subject_id": record.subject_id,
        "subject_name": name,
        "grade_level": record.grade_level,
        "semester": record.semester,
        "score": float(record.score),
    }


def achievement_data(item):
    return {key: getattr(item, key) for key in ("id", "title", "level", "year")}


def assessment_data(item):
    return {
        "id": item.id,
        "instrument_version": item.instrument_version,
        "scores": item.scores,
        "taken_at": item.taken_at,
    }


@router.get("", response_model=Envelope[ProfileOut])
def get_profile(user: User = Depends(student_user), db: Session = Depends(get_db)):
    return envelope(profile_data(profile_for(db, user)))


@router.put("", response_model=Envelope[ProfileOut])
def update_profile(
    body: ProfileIn, user: User = Depends(student_user), db: Session = Depends(get_db)
):
    profile = profile_for(db, user)
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    refresh_completeness(db, profile)
    return envelope(profile_data(profile))


@router.get("/subjects", response_model=Envelope[list[SubjectOut]])
def subjects(db: Session = Depends(get_db)):
    rows = db.scalars(select(Subject).order_by(Subject.name)).all()
    return envelope([{"id": row.id, "name": row.name} for row in rows])


@router.post("/academic-records", status_code=201, response_model=Envelope[AcademicOut])
def add_academic(
    body: AcademicIn, user: User = Depends(student_user), db: Session = Depends(get_db)
):
    profile = profile_for(db, user)
    subject = db.get(Subject, body.subject_id)
    if subject is None:
        raise HTTPException(404, "Mata pelajaran tidak ditemukan")
    record = AcademicRecord(student_profile_id=profile.id, **body.model_dump())
    db.add(record)
    try:
        refresh_completeness(db, profile)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Nilai untuk mapel, kelas, dan semester itu sudah ada") from None
    return envelope(academic_data(record, subject.name))


@router.get("/academic-records", response_model=Envelope[list[AcademicOut]])
def list_academic(user: User = Depends(student_user), db: Session = Depends(get_db)):
    profile = profile_for(db, user)
    rows = db.execute(
        select(AcademicRecord, Subject.name)
        .join(Subject)
        .where(AcademicRecord.student_profile_id == profile.id)
        .order_by(AcademicRecord.grade_level, AcademicRecord.semester, Subject.name)
    ).all()
    return envelope([academic_data(record, name) for record, name in rows])


def owned_record(db, profile, id):
    item = db.scalar(
        select(AcademicRecord).where(
            AcademicRecord.id == id, AcademicRecord.student_profile_id == profile.id
        )
    )
    if item is None:
        raise HTTPException(404, "Nilai tidak ditemukan")
    return item


@router.put("/academic-records/{id}", response_model=Envelope[AcademicOut])
def update_academic(
    id: UUID,
    body: AcademicScoreIn,
    user: User = Depends(student_user),
    db: Session = Depends(get_db),
):
    profile = profile_for(db, user)
    record = owned_record(db, profile, id)
    record.score = body.score
    record.verification_status = "belum"
    record.verified_by = None
    db.commit()
    return envelope(academic_data(record, db.get(Subject, record.subject_id).name))


@router.delete("/academic-records/{id}", response_model=Envelope[DeletedOut])
def delete_academic(id: UUID, user: User = Depends(student_user), db: Session = Depends(get_db)):
    profile = profile_for(db, user)
    db.delete(owned_record(db, profile, id))
    refresh_completeness(db, profile)
    return envelope({"deleted": True})


@router.post("/achievements", status_code=201, response_model=Envelope[AchievementOut])
def add_achievement(
    body: AchievementIn, user: User = Depends(student_user), db: Session = Depends(get_db)
):
    profile = profile_for(db, user)
    item = Achievement(student_profile_id=profile.id, **body.model_dump())
    db.add(item)
    db.commit()
    return envelope(achievement_data(item))


@router.get("/achievements", response_model=Envelope[list[AchievementOut]])
def list_achievements(user: User = Depends(student_user), db: Session = Depends(get_db)):
    profile = profile_for(db, user)
    items = db.scalars(
        select(Achievement)
        .where(Achievement.student_profile_id == profile.id)
        .order_by(Achievement.year.desc(), Achievement.title)
    ).all()
    return envelope([achievement_data(item) for item in items])


@router.delete("/achievements/{id}", response_model=Envelope[DeletedOut])
def delete_achievement(id: UUID, user: User = Depends(student_user), db: Session = Depends(get_db)):
    profile = profile_for(db, user)
    item = db.scalar(
        select(Achievement).where(
            Achievement.id == id, Achievement.student_profile_id == profile.id
        )
    )
    if item is None:
        raise HTTPException(404, "Prestasi tidak ditemukan")
    db.delete(item)
    db.commit()
    return envelope({"deleted": True})


@router.post("/interest-assessment", status_code=201, response_model=Envelope[AssessmentOut])
def add_assessment(
    body: AssessmentIn, user: User = Depends(student_user), db: Session = Depends(get_db)
):
    profile = profile_for(db, user)
    item = InterestAssessment(
        student_profile_id=profile.id,
        instrument_version=body.instrument_version,
        scores=body.scores.model_dump(),
    )
    db.add(item)
    refresh_completeness(db, profile)
    return envelope(assessment_data(item))


@router.get("/interest-assessment/latest", response_model=Envelope[AssessmentOut])
def latest_assessment(user: User = Depends(student_user), db: Session = Depends(get_db)):
    profile = profile_for(db, user)
    item = db.scalar(
        select(InterestAssessment)
        .where(InterestAssessment.student_profile_id == profile.id)
        .order_by(InterestAssessment.taken_at.desc(), InterestAssessment.id.desc())
        .limit(1)
    )
    if item is None:
        raise HTTPException(404, "Hasil tes minat belum tersedia")
    return envelope(assessment_data(item))
