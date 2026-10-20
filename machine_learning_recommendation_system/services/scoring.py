"""Fungsi murni, bebas database. Semua skor menggunakan skala 0-100."""

from math import asin, cos, radians, sin, sqrt

from app.schemas import DIMENSIONS

MODEL_VERSION = "rule-based-v1.0"
FACTOR_NAMES = {
    "akademik": "Kecocokan nilai akademik",
    "minat": "Kecocokan minat RIASEC",
    "peluang": "Posisi nilai terhadap histori",
    "jarak": "Kedekatan sekolah",
    "biaya": "Kesesuaian biaya bulanan",
}


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(clamp(a, 0, 1)))


def academic_score(student_average, historical_average):
    return clamp(100 - abs(student_average - historical_average) * 5)


def cosine_score(student, program):
    a = [student[x] for x in DIMENSIONS]
    b = [program[x] for x in DIMENSIONS]
    denominator = sqrt(sum(x * x for x in a)) * sqrt(sum(x * x for x in b))
    return clamp(100 * sum(x * y for x, y in zip(a, b)) / denominator) if denominator else 0.0


def distance_score(distance, maximum):
    return clamp(100 * (1 - distance / maximum))


def cost_score(monthly_cost, budget):
    if monthly_cost <= budget:
        return 100.0
    return clamp(100 * budget / monthly_cost)


def monthly_equivalent(cost):
    # other_fee adalah biaya berulang per periode yang sama dengan SPP.
    total = float(cost.tuition_per_period) + float(cost.other_fee)
    return total / (6 if cost.period_type == "semester" else 1)


def chance_score(value, minimum, average, maximum):
    # Titik jangkar heuristik: minimum->35, rata-rata->65, maksimum->85.
    # Histori identik: jadikan satu jangkar 65 untuk menghindari pembagian nol.
    points = [(minimum, 35.0), (average, 65.0), (maximum, 85.0)]
    grouped = {}
    for x, y in points:
        grouped.setdefault(x, []).append(y)
    anchors = [(x, sum(ys) / len(ys)) for x, ys in sorted(grouped.items())]
    if len(anchors) == 1:
        return clamp(65 + 5 * (value - average), 5, 95)
    if value < anchors[0][0]:
        return clamp(anchors[0][1] + 5 * (value - anchors[0][0]), 5, 95)
    if value > anchors[-1][0]:
        return clamp(anchors[-1][1] + 5 * (value - anchors[-1][0]), 5, 95)
    for (x1, y1), (x2, y2) in zip(anchors, anchors[1:]):
        if x1 <= value <= x2:
            return clamp(y1 + (y2 - y1) * (value - x1) / (x2 - x1), 5, 95)
    return anchors[-1][1]


def aggregate_history(rows):
    # Satu jalur saja. Tahun terbaru mendapat bobot lebih besar.
    years = sorted({r.year for r in rows})
    weights = {year: index + 1 for index, year in enumerate(years)}
    denominator = sum(weights[r.year] for r in rows)
    values = {
        key: sum(float(getattr(r, key)) * weights[r.year] for r in rows) / denominator
        for key in ("min_score", "avg_score", "max_score")
    }
    values["year_count"] = len(years)
    return values


def chance_range(midpoint, year_count, partial_profile=False):
    # Rentang ketidakpastian heuristik, bukan interval kepercayaan statistik.
    margin = 10 + max(0, 3 - year_count) * 5 + (5 if partial_profile else 0)
    return round(clamp(midpoint - margin), 2), round(clamp(midpoint + margin), 2)


def chance_category(score):
    return "ambisius" if score < 35 else "realistis" if score <= 70 else "aman"


def weighted_total(scores, weights):
    return round(clamp(sum(scores[x] * weights[x] for x in weights)), 2)


def explain(scores, details, warning):
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    positive = [f"{FACTOR_NAMES[x]} {scores[x]:.1f}/100: {details[x]}" for x in ordered[:2]]
    negative = [
        f"Faktor dengan skor relatif terendah: {FACTOR_NAMES[x]} {scores[x]:.1f}/100: {details[x]}"
        for x in ordered[-2:]
    ]
    negative[-1] += " " + warning
    return {"positive": positive, "negative": negative}
