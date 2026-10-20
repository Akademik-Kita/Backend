from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import InterestScores, StrictModel


class ProfileOut(BaseModel):
    id: UUID
    user_id: UUID
    current_school_name: str | None
    grade: int | None
    domisili_kecamatan: str | None
    latitude: float | None
    longitude: float | None
    budget_max_per_bulan: int | None
    max_distance_km: float | None
    preferred_ownership: list[str] | None
    profile_completeness: int


class SubjectOut(BaseModel):
    id: UUID
    name: str


class AcademicOut(BaseModel):
    id: UUID
    subject_id: UUID
    subject_name: str
    grade_level: int
    semester: int
    score: float


class AchievementOut(BaseModel):
    id: UUID
    title: str
    level: str
    year: int


class AssessmentOut(BaseModel):
    id: UUID
    instrument_version: str
    scores: dict[str, float]
    taken_at: datetime


class DeletedOut(BaseModel):
    deleted: Literal[True]


class ProfileIn(StrictModel):
    current_school_name: str | None = Field(default=None, max_length=200)
    grade: int | None = Field(default=None, ge=7, le=9)
    domisili_kecamatan: str | None = Field(default=None, max_length=120)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    budget_max_per_bulan: int | None = Field(default=None, ge=0)
    max_distance_km: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    preferred_ownership: list[Literal["negeri", "swasta"]] | None = None

    @field_validator("preferred_ownership")
    @classmethod
    def no_duplicates(cls, value):
        if value is not None and (not value or len(set(value)) != len(value)):
            raise ValueError("Pilih setidaknya satu jenis sekolah tanpa duplikasi")
        return value


class AcademicIn(StrictModel):
    subject_id: UUID
    grade_level: int = Field(ge=7, le=9)
    semester: int = Field(ge=1, le=2)
    score: float = Field(ge=0, le=100, allow_inf_nan=False)


class AcademicScoreIn(StrictModel):
    score: float = Field(ge=0, le=100, allow_inf_nan=False)


class AchievementIn(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    level: Literal["sekolah", "kecamatan", "kota", "provinsi", "nasional", "internasional"]
    year: int = Field(ge=1900, le=2200)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Judul prestasi wajib diisi")
        return value


class AssessmentIn(StrictModel):
    instrument_version: Literal["riasec-lite-v1"]
    scores: InterestScores
