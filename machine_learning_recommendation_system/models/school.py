from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import JSON_TYPE, Base, IdMixin


class Region(IdMixin, Base):
    __tablename__ = "regions"
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(20), default="kecamatan")
    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("regions.id"))
    __table_args__ = (CheckConstraint("type IN ('provinsi','kab_kota','kecamatan','kelurahan')"),)


class Institution(IdMixin, Base):
    __tablename__ = "institutions"
    name: Mapped[str] = mapped_column(String(200), index=True)
    institution_type: Mapped[str] = mapped_column(String(10), default="SMA")
    ownership: Mapped[str] = mapped_column(String(10))
    npsn_or_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    region_id: Mapped[UUID] = mapped_column(ForeignKey("regions.id"))
    address: Mapped[str] = mapped_column(Text)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    accreditation: Mapped[str] = mapped_column(String(20), index=True)
    website: Mapped[str | None] = mapped_column(String(500))
    contact: Mapped[str | None] = mapped_column(String(100))
    data_source: Mapped[str] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    region: Mapped[Region] = relationship(lazy="raise")
    programs: Mapped[list["Program"]] = relationship(back_populates="institution", lazy="raise")
    facilities: Mapped[list["Facility"]] = relationship(lazy="raise")
    __table_args__ = (
        CheckConstraint("ownership IN ('negeri','swasta')"),
        CheckConstraint("latitude BETWEEN -90 AND 90"),
        CheckConstraint("longitude BETWEEN -180 AND 180"),
        Index("ix_institutions_type_region", "institution_type", "region_id"),
    )


class Program(IdMixin, Base):
    __tablename__ = "programs"
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(150))
    program_type: Mapped[str] = mapped_column(String(40), default="peminatan_sma")
    degree_level: Mapped[str | None] = mapped_column(String(20))
    accreditation: Mapped[str | None] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text, default="")
    interest_profile: Mapped[dict] = mapped_column(JSON_TYPE)
    required_subjects: Mapped[list] = mapped_column(JSON_TYPE, default=list)
    institution: Mapped[Institution] = relationship(back_populates="programs", lazy="raise")
    tracks: Mapped[list["AdmissionTrack"]] = relationship(lazy="raise")
    costs: Mapped[list["Cost"]] = relationship(lazy="raise")
    __table_args__ = (UniqueConstraint("institution_id", "name"),)


class AdmissionTrack(IdMixin, Base):
    __tablename__ = "admission_tracks"
    program_id: Mapped[UUID] = mapped_column(ForeignKey("programs.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    quota: Mapped[int] = mapped_column(Integer)
    rules: Mapped[dict] = mapped_column(JSON_TYPE, default=dict)
    history: Mapped[list["AdmissionHistory"]] = relationship(lazy="raise")
    __table_args__ = (UniqueConstraint("program_id", "name"), CheckConstraint("quota >= 0"))


class AdmissionHistory(IdMixin, Base):
    __tablename__ = "admission_history"
    admission_track_id: Mapped[UUID] = mapped_column(ForeignKey("admission_tracks.id"))
    year: Mapped[int] = mapped_column(Integer)
    applicants: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[int] = mapped_column(Integer)
    min_score: Mapped[float] = mapped_column(Float)
    avg_score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
    score_distribution: Mapped[dict | None] = mapped_column(JSON_TYPE)
    source: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("admission_track_id", "year"),
        CheckConstraint(
            "min_score >= 0 AND min_score <= avg_score AND avg_score <= max_score AND max_score <= 100"
        ),
        CheckConstraint("accepted >= 0 AND applicants >= accepted"),
    )


class Cost(IdMixin, Base):
    __tablename__ = "costs"
    program_id: Mapped[UUID] = mapped_column(ForeignKey("programs.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(9))
    entrance_fee: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tuition_per_period: Mapped[float] = mapped_column(Numeric(14, 2))
    other_fee: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    period_type: Mapped[str] = mapped_column(String(10))
    scholarship_info: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("program_id", "academic_year"),
        CheckConstraint("entrance_fee >= 0 AND tuition_per_period >= 0 AND other_fee >= 0"),
        CheckConstraint("period_type IN ('bulan','semester')"),
    )


class Facility(IdMixin, Base):
    __tablename__ = "facilities"
    institution_id: Mapped[UUID] = mapped_column(ForeignKey("institutions.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("institution_id", "name"),)
