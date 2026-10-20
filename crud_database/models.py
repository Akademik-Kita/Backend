from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import JSON_TYPE, Base, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(500))
    full_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    profile: Mapped["StudentProfile | None"] = relationship(back_populates="user", lazy="raise")
    __table_args__ = (
        CheckConstraint("role IN ('siswa','orang_tua')"),
        Index("ix_users_email", "email"),
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    current_school_name: Mapped[str | None] = mapped_column(String(200))
    grade: Mapped[int | None] = mapped_column(Integer)
    domisili_kecamatan: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    budget_max_per_bulan: Mapped[int | None] = mapped_column(Integer)
    max_distance_km: Mapped[float | None] = mapped_column(Float)
    preferred_ownership: Mapped[list | None] = mapped_column(JSON_TYPE)
    profile_completeness: Mapped[int] = mapped_column(Integer, default=0)
    user: Mapped[User] = relationship(back_populates="profile", lazy="raise")
    __table_args__ = (
        CheckConstraint("grade BETWEEN 7 AND 9 OR grade IS NULL"),
        CheckConstraint("latitude BETWEEN -90 AND 90 OR latitude IS NULL"),
        CheckConstraint("longitude BETWEEN -180 AND 180 OR longitude IS NULL"),
        CheckConstraint("budget_max_per_bulan >= 0 OR budget_max_per_bulan IS NULL"),
        CheckConstraint("max_distance_km > 0 OR max_distance_km IS NULL"),
        CheckConstraint("profile_completeness BETWEEN 0 AND 100"),
    )


class Subject(Base):
    __tablename__ = "subjects"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str] = mapped_column(String(30), default="inti")


class AcademicRecord(Base):
    __tablename__ = "academic_records"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    subject_id: Mapped[UUID] = mapped_column(ForeignKey("subjects.id"))
    grade_level: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Numeric(5, 2))
    verification_status: Mapped[str] = mapped_column(String(20), default="belum")
    verified_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))
    subject: Mapped[Subject] = relationship(lazy="raise")
    __table_args__ = (
        UniqueConstraint("student_profile_id", "subject_id", "grade_level", "semester"),
        CheckConstraint("grade_level BETWEEN 7 AND 9"),
        CheckConstraint("semester IN (1,2)"),
        CheckConstraint("score BETWEEN 0 AND 100"),
        CheckConstraint("verification_status IN ('belum','diverifikasi','ditolak')"),
    )


class Achievement(Base):
    __tablename__ = "achievements"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20))
    year: Mapped[int] = mapped_column(Integer)
    __table_args__ = (
        CheckConstraint(
            "level IN ('sekolah','kecamatan','kota','provinsi','nasional','internasional')"
        ),
    )


class InterestAssessment(Base):
    __tablename__ = "interest_assessments"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    student_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("student_profiles.id", ondelete="CASCADE"), index=True
    )
    instrument_version: Mapped[str] = mapped_column(String(60))
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    scores: Mapped[dict] = mapped_column(JSON_TYPE)
