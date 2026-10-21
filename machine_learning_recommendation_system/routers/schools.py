from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models import Institution, Region
from app.schemas import Envelope, ErrorEnvelope, HistoryOut, Ownership, SchoolDetail, SchoolSummary
from machine_learning_recommendation_system.dependencies import get_optional_user
from machine_learning_recommendation_system.services.catalog import detail, school_query, summary
from machine_learning_recommendation_system.services.student import load_location

router = APIRouter(
    prefix="/schools",
    tags=["Data SMA"],
    responses={status: {"model": ErrorEnvelope} for status in (401, 404, 422, 500, 503)},
)


def location_for(db, user_id):
    return load_location(db, user_id) if user_id else None


@router.get("", response_model=Envelope[list[SchoolSummary]])
def list_schools(
    kecamatan: str | None = None,
    search: str | None = Query(None, max_length=200),
    ownership: Ownership | None = None,
    accreditation: str | None = None,
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
    user_id: UUID | None = Depends(get_optional_user),
):
    query = school_query()
    if kecamatan and kecamatan.strip():
        query = query.join(Region).where(Region.name.ilike(kecamatan.strip()))
    if search and search.strip():
        keyword = search.strip()
        regions = (
            select(Region.id)
            .where(Region.name.icontains(keyword, autoescape=True))
            .cte("search_regions", recursive=True)
        )
        regions = regions.union(select(Region.id).where(Region.parent_id == regions.c.id))
        query = query.where(
            or_(
                Institution.name.icontains(keyword, autoescape=True),
                Institution.npsn_or_code.icontains(keyword, autoescape=True),
                Institution.region_id.in_(select(regions.c.id)),
            )
        )
    if ownership:
        query = query.where(Institution.ownership == ownership)
    if accreditation:
        query = query.where(Institution.accreditation == accreditation)
    # Ukuran halaman tetap 10, response.data tetap array sesuai kontrak.
    schools = db.scalars(
        query.order_by(Institution.name, Institution.id).offset((page - 1) * 10).limit(10)
    ).all()
    location = location_for(db, user_id)
    return {"data": [summary(s, location) for s in schools], "message": "Daftar SMA"}


# Harus sebelum /{id}; agar 'compare' tidak diparse sebagai UUID.
@router.get("/compare", response_model=Envelope[list[SchoolDetail]])
def compare_schools(
    ids: str = Query(..., max_length=200),
    db: Session = Depends(get_db),
    user_id: UUID | None = Depends(get_optional_user),
):
    try:
        school_ids = [UUID(x.strip()) for x in ids.split(",")]
    except ValueError:
        raise HTTPException(422, "ids harus berisi UUID yang dipisahkan koma") from None
    if not 1 <= len(school_ids) <= 4 or len(set(school_ids)) != len(school_ids):
        raise HTTPException(422, "Pilih 1 sampai 4 ID sekolah unik")
    schools = db.scalars(school_query().where(Institution.id.in_(school_ids))).all()
    by_id = {s.id: s for s in schools}
    if len(by_id) != len(school_ids):
        raise HTTPException(404, "Salah satu SMA tidak ditemukan")
    location = location_for(db, user_id)
    return {"data": [detail(by_id[x], location) for x in school_ids], "message": "Perbandingan SMA"}


@router.get(
    "/{id}/jurusan/{jurusan_id}/riwayat-penerimaan", response_model=Envelope[list[HistoryOut]]
)
def history(
    id: UUID,
    jurusan_id: UUID,
    db: Session = Depends(get_db),
):
    school = db.scalar(school_query(include_history=True).where(Institution.id == id))
    if school is None:
        raise HTTPException(404, "SMA tidak ditemukan")
    program = next((p for p in school.programs if p.id == jurusan_id), None)
    if program is None:
        raise HTTPException(404, "Jurusan tidak ditemukan pada SMA ini")
    year = datetime.now(ZoneInfo("Asia/Jakarta")).year
    records = [
        {
            "year": h.year,
            "jalur": t.name,
            "nilai_minimum": h.min_score,
            "nilai_rata2": h.avg_score,
            "nilai_maksimum": h.max_score,
            "quota": t.quota,
            "applicants": h.applicants,
            "accepted": h.accepted,
            "source": h.source,
        }
        for t in program.tracks
        for h in t.history
        if year - 3 <= h.year < year
    ]
    records.sort(key=lambda h: (-h["year"], h["jalur"]))
    return {"data": records, "message": "Histori tiga tahun kalender selesai terakhir"}


@router.get("/{id}", response_model=Envelope[SchoolDetail])
def school_detail(
    id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID | None = Depends(get_optional_user),
):
    school = db.scalar(school_query().where(Institution.id == id))
    if school is None:
        raise HTTPException(404, "SMA tidak ditemukan")
    return {"data": detail(school, location_for(db, user_id)), "message": "Detail SMA"}
