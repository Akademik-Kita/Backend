"""Impor JSON tervalidasi dan atomik. Tidak menyediakan endpoint admin publik."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.models import (
    AdmissionHistory,
    AdmissionTrack,
    Cost,
    Facility,
    Institution,
    Program,
    Region,
)
from app.schemas import InterestScores, StrictModel


class RegionInput(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=120)
    type: Literal["provinsi", "kab_kota", "kecamatan", "kelurahan"] = "kecamatan"
    parent_id: UUID | None = None


class RulesInput(StrictModel):
    score_basis: Literal["academic_average_0_100"]
    supported_grades: list[Literal[7, 8, 9]] = Field(
        default_factory=lambda: [7, 8, 9], min_length=1
    )
    min_academic_score: float = Field(default=0, ge=0, le=100)
    max_distance_km: float | None = Field(default=None, gt=0)


class HistoryInput(StrictModel):
    id: UUID
    year: int = Field(ge=2000, le=2100)
    applicants: int = Field(ge=0)
    accepted: int = Field(ge=0)
    min_score: float = Field(ge=0, le=100)
    avg_score: float = Field(ge=0, le=100)
    max_score: float = Field(ge=0, le=100)
    source: str = Field(min_length=1)
    score_distribution: dict | None = None

    @model_validator(mode="after")
    def ordered(self):
        if not self.min_score <= self.avg_score <= self.max_score:
            raise ValueError("Histori harus minimum <= rata-rata <= maksimum")
        if self.accepted > self.applicants:
            raise ValueError("Jumlah diterima tidak boleh melebihi jumlah pendaftar")
        return self


class TrackInput(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=100)
    quota: int = Field(ge=0)
    rules: RulesInput
    history: list[HistoryInput]

    @model_validator(mode="after")
    def unique_years(self):
        if len({h.year for h in self.history}) != len(self.history):
            raise ValueError("Tahun histori jalur harus unik")
        return self


class CostInput(StrictModel):
    id: UUID
    academic_year: str
    entrance_fee: float = Field(default=0, ge=0)
    tuition_per_period: float = Field(ge=0)
    other_fee: float = Field(default=0, ge=0)
    period_type: Literal["bulan", "semester"]
    scholarship_info: str | None = None

    @field_validator("academic_year")
    @classmethod
    def validate_year(cls, value):
        if not re.fullmatch(r"20\d{2}/20\d{2}", value) or int(value[5:]) != int(value[:4]) + 1:
            raise ValueError("academic_year harus YYYY/YYYY+1, contoh 2026/2027")
        return value


class FacilityInput(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=100)


class ProgramInput(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=150)
    program_type: Literal["peminatan_sma"] = "peminatan_sma"
    degree_level: str | None = None
    accreditation: str | None = None
    description: str = ""
    interest_profile: InterestScores
    required_subjects: list[str] = Field(default_factory=list)
    tracks: list[TrackInput]
    costs: list[CostInput]

    @model_validator(mode="after")
    def validate_children(self):
        if not any(self.interest_profile.model_dump().values()):
            raise ValueError("Vektor minat jurusan tidak boleh semuanya nol")
        for values, field in ((self.tracks, "name"), (self.costs, "academic_year")):
            if len({getattr(v, field) for v in values}) != len(values):
                raise ValueError(f"Duplikasi {field} pada program")
        return self


class SchoolInput(StrictModel):
    id: UUID
    name: str = Field(min_length=1, max_length=200)
    institution_type: Literal["SMA"] = "SMA"
    ownership: Literal["negeri", "swasta"]
    npsn_or_code: str | None = None
    region_id: UUID
    address: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accreditation: str
    website: str | None = None
    contact: str | None = None
    data_source: str = Field(min_length=1)
    last_verified_at: datetime | None = None
    programs: list[ProgramInput] = Field(default_factory=list)
    facilities: list[FacilityInput]

    @model_validator(mode="after")
    def unique_children(self):
        for values in (self.programs, self.facilities):
            if len({v.name for v in values}) != len(values):
                raise ValueError("Nama program/fasilitas harus unik dalam sekolah")
        return self


class CatalogInput(StrictModel):
    regions: list[RegionInput]
    schools: list[SchoolInput]

    @model_validator(mode="after")
    def references_and_ids(self):
        regions = {r.id for r in self.regions}
        if any(s.region_id not in regions for s in self.schools):
            raise ValueError("region_id sekolah harus tersedia pada daftar regions")
        parents = {r.id: r.parent_id for r in self.regions}
        for r in self.regions:
            seen = set()
            node = r.id
            while node is not None:
                if node in seen or node not in parents:
                    raise ValueError(
                        "Hierarki wilayah mengandung siklus atau parent_id tidak ditemukan"
                    )
                seen.add(node)
                node = parents[node]
        groups = {
            "regions": self.regions,
            "schools": self.schools,
            "programs": [],
            "tracks": [],
            "history": [],
            "costs": [],
            "facilities": [],
        }
        codes = [s.npsn_or_code for s in self.schools if s.npsn_or_code is not None]
        if len(codes) != len(set(codes)):
            raise ValueError("npsn_or_code harus unik")
        for s in self.schools:
            groups["programs"].extend(s.programs)
            groups["facilities"].extend(s.facilities)
            for p in s.programs:
                groups["tracks"].extend(p.tracks)
                groups["costs"].extend(p.costs)
                for t in p.tracks:
                    groups["history"].extend(t.history)
        for name, items in groups.items():
            if len({i.id for i in items}) != len(items):
                raise ValueError(f"Duplikasi id pada {name}")
        return self


def load_catalog(path):
    return CatalogInput.model_validate(json.loads(Path(path).read_text(encoding="utf-8")))


def append_catalog(db, catalog: CatalogInput):
    """Add missing identities by NPSN without overwriting curated school data."""
    from sqlalchemy import select

    regions = {
        (r.type, r.parent_id, r.name.strip().casefold()): r.id for r in db.scalars(select(Region))
    }
    mapped = {}
    pending = list(catalog.regions)
    while pending:
        ready = [r for r in pending if r.parent_id is None or r.parent_id in mapped]
        for region in ready:
            parent = mapped.get(region.parent_id)
            key = (region.type, parent, region.name.strip().casefold())
            if key not in regions:
                db.add(Region(**{**region.model_dump(), "parent_id": parent}))
                regions[key] = region.id
            mapped[region.id] = regions[key]
            pending.remove(region)
        db.flush()
    codes = set(db.scalars(select(Institution.npsn_or_code)))
    added = []
    for school in catalog.schools:
        if not school.npsn_or_code:
            raise ValueError("Penambahan sekolah membutuhkan NPSN")
        if school.npsn_or_code in codes:
            continue
        values = school.model_dump(exclude={"programs", "facilities"})
        values["region_id"] = mapped[school.region_id]
        db.add(Institution(**values))
        added.append(school.id)
        codes.add(school.npsn_or_code)
    db.flush()
    return added


def upsert(db, model, values, parent=None):
    obj = db.get(model, values["id"])
    if obj is None:
        obj = model(**values)
        db.add(obj)
    else:
        if parent:
            key = next(iter(parent))
            if getattr(obj, key) != parent[key]:
                raise ValueError(f"ID {values['id']} sudah dimiliki induk lain")
        for key, value in values.items():
            setattr(obj, key, value)
    # Induk harus tersimpan sebelum data turunannya; kegagalan membatalkan seluruh impor.
    db.flush()


def import_catalog(db, catalog: CatalogInput):
    try:
        # Masukkan wilayah induk lebih dulu agar foreign key terpenuhi.
        pending = list(catalog.regions)
        inserted = set()
        while pending:
            for r in pending[:]:
                if r.parent_id is None or r.parent_id in inserted:
                    upsert(db, Region, r.model_dump())
                    inserted.add(r.id)
                    pending.remove(r)
        for s in catalog.schools:
            upsert(db, Institution, s.model_dump(exclude={"programs", "facilities"}))
            for f in s.facilities:
                parent = {"institution_id": s.id}
                upsert(db, Facility, {**f.model_dump(), **parent}, parent)
            for p in s.programs:
                parent = {"institution_id": s.id}
                upsert(db, Program, {**p.model_dump(exclude={"tracks", "costs"}), **parent}, parent)
                for c in p.costs:
                    parent = {"program_id": p.id}
                    upsert(db, Cost, {**c.model_dump(), **parent}, parent)
                for t in p.tracks:
                    parent = {"program_id": p.id}
                    values = t.model_dump(exclude={"history"})
                    values["rules"] = t.rules.model_dump(exclude_none=True)
                    upsert(db, AdmissionTrack, {**values, **parent}, parent)
                    for h in t.history:
                        parent = {"admission_track_id": t.id}
                        upsert(db, AdmissionHistory, {**h.model_dump(), **parent}, parent)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "schools": len(catalog.schools),
        "programs": sum(len(s.programs) for s in catalog.schools),
    }
