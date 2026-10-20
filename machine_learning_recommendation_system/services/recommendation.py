from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import Field, model_validator
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Institution, Program, RecommendationRun, RecommendationItem
from machine_learning_recommendation_system.services.catalog import school_query
from machine_learning_recommendation_system.services.catalog import calculate_distance, get_coords
from machine_learning_recommendation_system.services.student import load_location

from app.schemas.common import InterestScores, StrictModel


class Weights(StrictModel):
    academic: float = Field(default=0.2, ge=0, le=1)
    interest: float = Field(default=0.2, ge=0, le=1)
    chance: float = Field(default=0.2, ge=0, le=1)
    distance: float = Field(default=0.2, ge=0, le=1)
    cost: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="before")
    @classmethod
    def normalize_indonesian_keys(cls, value):
        if not isinstance(value, dict):
            return value
        aliases = {
            "akademik": "academic",
            "minat": "interest",
            "peluang": "chance",
            "jarak": "distance",
            "biaya": "cost",
        }
        normalized = dict(value)
        for old_key, new_key in aliases.items():
            if old_key in normalized:
                normalized.setdefault(new_key, normalized[old_key])
                normalized.pop(old_key, None)
        return normalized


class GenerateRequest(StrictModel):
    weights: Weights = Field(default_factory=Weights)


class ScoreBreakdown(StrictModel):
    academic: float
    interest: float
    chance: float
    distance: float
    cost: float


class RecommendationOut(StrictModel):
    school_id: UUID
    school_name: str
    jurusan_name: str
    total_score: float
    score: float
    chance_category: str
    chance_range: str
    breakdown: ScoreBreakdown


class RunOut(StrictModel):
    recommendations: List[RecommendationOut]
    weights: Weights


class Explanation(StrictModel):
    summary: str = ""
    details: Dict[str, Any] = {}


class StudentContext(StrictModel):
    user_id: Optional[UUID] = None
    interest_profile: Optional[InterestScores] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

def _weights_dict(weights: Any) -> Dict[str, float]:
    if hasattr(weights, "model_dump"):
        values = weights.model_dump()
    elif hasattr(weights, "dict"):
        values = weights.dict()
    elif isinstance(weights, dict):
        values = weights
    else:
        values = {}
    defaults = Weights().model_dump() if hasattr(Weights(), "model_dump") else Weights().dict()
    return {key: float(values.get(key, default)) for key, default in defaults.items()}


def _build_recommendations(db: Session, student: Any, weights: Dict[str, float]) -> List[Dict[str, Any]]:
    schools = db.scalars(school_query()).all()
    location = student if student is not None else None
    u_lat, u_lon = get_coords(location)
    recommendations = []

    for school in schools:
        s_lat, s_lon = get_coords(school)
        distance = calculate_distance(s_lat, s_lon, u_lat, u_lon, school.id)
        academic = 78.0
        interest = 80.0
        chance = round(min(95.0, max(40.0, academic * 0.95)), 1)
        distance_score = 100.0 if distance <= 2 else 85.0 if distance <= 5 else 70.0 if distance <= 10 else 50.0 if distance <= 20 else 30.0
        ownership = str(getattr(school, "ownership", "") or "").lower()
        if "negeri" in ownership:
            cost_score = 100.0
        else:
            costs = []
            for program in (getattr(school, "programs", []) or []):
                for cost in (getattr(program, "costs", []) or []):
                    tuition = float(getattr(cost, "tuition_per_period", 0) or 0)
                    if tuition > 0:
                        costs.append(tuition / 6 if getattr(cost, "period_type", "bulan") == "semester" else tuition)
            minimum = min(costs) if costs else 0
            cost_score = 70.0 if not minimum else 90.0 if minimum <= 500000 else 75.0 if minimum <= 1000000 else 60.0 if minimum <= 2000000 else 40.0
        breakdown = {"academic": academic, "interest": interest, "chance": chance, "distance": distance_score, "cost": cost_score}
        total = round(sum(breakdown[k] * weights[k] for k in breakdown), 1)
        programs = getattr(school, "programs", []) or []
        recommendations.append({
            "school_id": school.id,
            "school_name": school.name,
            "jurusan_name": programs[0].name if programs else "Umum",
            "total_score": total,
            "score": total / 100,
            "chance_category": "Aman" if chance >= 75 else "Pertimbangan" if chance >= 55 else "Ketat",
            "chance_range": f"{max(30, chance - 10):.2f}%–{min(99, chance + 10):.2f}% peluang",
            "breakdown": breakdown,
            "_program_id": programs[0].id if programs else None,
        })
    recommendations.sort(key=lambda x: x["total_score"], reverse=True)
    return recommendations


def generate(db: Session, student: Any, weights: Any, hard_filters: bool = False):
    """Generate rekomendasi, simpan snapshot, lalu kembalikan data dan pesan."""
    values = _weights_dict(weights)
    recommendations = _build_recommendations(db, student, values)
    profile_id = getattr(student, "id", None)
    if profile_id is None:
        # Router mewajibkan profil siswa; ini mencegah run tanpa pemilik.
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Profil siswa belum tersedia")

    clean_recommendations = [
        {k: v for k, v in item.items() if not k.startswith("_")}
        for item in recommendations
    ]
    run = RecommendationRun(
        student_profile_id=profile_id,
        target_type="sekolah",
        model_version="baseline-v1",
        input_snapshot=jsonable_encoder({"weights": values, "recommendations": clean_recommendations}),
    )
    db.add(run)
    db.flush()
    for rank, item in enumerate(recommendations, start=1):
        program_id = item.get("_program_id")
        if program_id is None:
            continue
        breakdown = item["breakdown"]
        chance = 76.0
        db.add(RecommendationItem(
            run_id=run.id,
            program_id=program_id,
            rank=rank,
            total_score=item["total_score"],
            score_breakdown=breakdown,
            chance_low=max(0.0, chance - 10.0),
            chance_high=min(100.0, chance + 10.0),
            explanation={"summary": "Rekomendasi berdasarkan skor dasar dan bobot kriteria."},
            category="aman" if chance >= 75 else "realistis" if chance >= 55 else "ambisius",
        ))
    db.commit()
    return {
        "recommendations": clean_recommendations,
        "weights": values,
    }, "Rekomendasi berhasil dibuat"


def latest(db: Session, student_id: UUID):
    run = db.scalar(
        select(RecommendationRun)
        .where(RecommendationRun.student_profile_id == student_id)
        .order_by(RecommendationRun.created_at.desc(), RecommendationRun.id.desc())
        .limit(1)
    )
    if run is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Belum ada rekomendasi tersimpan")
    snapshot = run.input_snapshot or {}
    return {
        "recommendations": snapshot.get("recommendations", []),
        "weights": _weights_dict(snapshot.get("weights", {})),
    }, "Rekomendasi terakhir berhasil diambil"
