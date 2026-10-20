from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import InterestScores, Ownership


class SchoolSummary(BaseModel):
    id: UUID
    name: str
    ownership: Ownership
    accreditation: str
    kecamatan: str
    latitude: float
    longitude: float
    distance_km: float | None
    jurusan_tersedia: list[str]
    biaya_per_bulan: str | None = None
    score: float | None = None
    skor_rekomendasi: str | float | None = None


class CostOut(BaseModel):
    academic_year: str
    entrance_fee: float
    tuition_per_period: float
    other_fee: float
    period_type: Literal["bulan", "semester"]
    scholarship_info: str | None
    monthly_equivalent: float


class TrackOut(BaseModel):
    id: UUID
    name: str
    quota: int
    rules: dict


class ProgramOut(BaseModel):
    id: UUID
    name: str
    program_type: str
    description: str
    interest_profile: InterestScores
    required_subjects: list[str]
    jalur_seleksi: list[TrackOut]
    biaya: list[CostOut]


class SchoolDetail(SchoolSummary):
    institution_type: str
    npsn_or_code: str | None
    address: str
    website: str | None
    contact: str | None
    data_source: str
    last_verified_at: datetime | None
    jurusan: list[ProgramOut]
    biaya: list[CostOut]
    fasilitas: list[str]


class HistoryOut(BaseModel):
    year: int
    jalur: str
    nilai_minimum: float
    nilai_rata2: float
    nilai_maksimum: float