import math
from typing import Any, Dict, List, Optional
from uuid import uuid4, UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Institution, Program, Cost
from machine_learning_recommendation_system.services.catalog import school_query, calculate_distance, get_coords
from machine_learning_recommendation_system.services.student import load_location


def calculate_academic_score(student_records: List[Any], program: Any) -> float:
    if not student_records:
        return 75.0
    scores = [float(r.score) for r in student_records if getattr(r, 'score', None) is not None]
    if not scores:
        return 75.0
    avg_score = sum(scores) / len(scores)
    return round(min(100.0, max(50.0, avg_score * 1.1)), 1)


def calculate_interest_score(student_assessment: Any, program: Any) -> float:
    if not student_assessment:
        return 80.0
    # Nilai baseline; belum dihitung dari profil minat.
    return 85.0


def calculate_chance_score(academic_score: float, program: Any) -> float:
    return round(min(95.0, max(40.0, academic_score * 0.95)), 1)


def calculate_cost_score(school: Institution) -> float:
    ownership = str(getattr(school, 'ownership', '') or '').lower()
    if 'negeri' in ownership:
        return 100.0
    
    monthly_costs = []
    for program in getattr(school, 'programs', []):
        for cost in getattr(program, 'costs', []):
            tuition = float(getattr(cost, 'tuition_per_period', 0) or 0)
            if tuition > 0:
                period = getattr(cost, 'period_type', 'bulan') or 'bulan'
                monthly = tuition / 6.0 if period == 'semester' else tuition
                monthly_costs.append(monthly)

    if not monthly_costs:
        return 70.0
    
    min_cost = min(monthly_costs)
    if min_cost <= 500000:
        return 90.0
    elif min_cost <= 1000000:
        return 75.0
    elif min_cost <= 2000000:
        return 60.0
    return 40.0


def calculate_distance_score(dist_km: float) -> float:
    if dist_km <= 2.0:
        return 100.0
    elif dist_km <= 5.0:
        return 85.0
    elif dist_km <= 10.0:
        return 70.0
    elif dist_km <= 20.0:
        return 50.0
    return 30.0


def generate(db: Session, user_id: UUID, weights: Dict[str, float]) -> Dict[str, Any]:
    try:
        schools = db.scalars(school_query()).all()
        if not schools:
            return {"recommendations": [], "weights": weights}

        location = load_location(db, user_id) if user_id else None
        u_lat, u_lon = get_coords(location)

        w_academic = float(weights.get("academic", 0.2))
        w_interest = float(weights.get("interest", 0.2))
        w_chance = float(weights.get("chance", 0.2))
        w_distance = float(weights.get("distance", 0.2))
        w_cost = float(weights.get("cost", 0.2))

        recommendations = []

        for school in schools:
            s_lat, s_lon = get_coords(school)
            dist_km = calculate_distance(s_lat, s_lon, u_lat, u_lon, school.id)

            # Skor akademik, minat, dan peluang di sini masih berupa nilai baseline.
            score_academic = 78.0
            score_interest = 95.0
            score_chance = 76.0
            score_distance = calculate_distance_score(dist_km)
            score_cost = calculate_cost_score(school)

            total_score = round(
                (score_academic * w_academic) +
                (score_interest * w_interest) +
                (score_chance * w_chance) +
                (score_distance * w_distance) +
                (score_cost * w_cost),
                1
            )

            chance_min = round(max(30.0, score_chance - 10.0), 2)
            chance_max = round(min(99.0, score_chance + 10.0), 2)
            chance_category = "Aman" if score_chance >= 75 else "Pertimbangan" if score_chance >= 55 else "Ketat"

            programs = getattr(school, 'programs', [])
            major_name = programs[0].name if programs and getattr(programs[0], 'name', None) else "Sains"

            recommendations.append({
                "school_id": school.id,
                "school_name": school.name,
                "jurusan_name": major_name,
                "total_score": total_score,
                "score": total_score / 100.0,
                "chance_category": chance_category,
                "chance_range": f"{chance_min}%–{chance_max}% peluang",
                "breakdown": {
                    "academic": score_academic,
                    "interest": score_interest,
                    "chance": score_chance,
                    "distance": score_distance,
                    "cost": score_cost
                }
            })

        recommendations.sort(key=lambda x: x["total_score"], reverse=True)

        return {
            "recommendations": recommendations,
            "weights": {
                "academic": w_academic,
                "interest": w_interest,
                "chance": w_chance,
                "distance": w_distance,
                "cost": w_cost
            }
        }
    except Exception as e:
        db.rollback()
        raise e
