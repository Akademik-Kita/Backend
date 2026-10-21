"""Fill missing school metadata with reproducible, explicitly labeled test data."""

import hashlib
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy.orm import selectinload

from app.models import AdmissionHistory, AdmissionTrack, Cost, Facility, Institution, Program
from machine_learning_recommendation_system.services.catalog import school_query

MARKER = "SIMULASI TAMBAHAN: biaya, jurusan, fasilitas dan histori untuk pengujian"


def number(key, low, high):
    return low + int(hashlib.sha256(key.encode()).hexdigest()[:16], 16) % (high - low + 1)


def stable(key):
    return uuid5(NAMESPACE_URL, "https://akademikkita.local/simulation/" + key)


def complete_school_data(db, year=None, school_ids=None):
    year = year or datetime.now(ZoneInfo("Asia/Jakarta")).year
    if not 2003 <= year <= 2099:
        raise ValueError("Tahun simulasi harus 2003–2099")
    query = school_query().options(
        selectinload(Institution.programs)
        .selectinload(Program.tracks)
        .selectinload(AdmissionTrack.history)
    )
    if school_ids is not None:
        query = query.where(Institution.id.in_(school_ids))
    schools = db.scalars(query).all()
    report = {
        "schools": 0,
        "skipped_dummy_identities": 0,
        "programs": 0,
        "costs": 0,
        "tracks": 0,
        "history": 0,
        "facilities": 0,
    }
    for school in schools:
        code = school.npsn_or_code or str(school.id)
        if code.upper().startswith("DEMO-") or school.data_source.upper().startswith(
            ("SINTETIS:", "DUMMY:")
        ):
            report["skipped_dummy_identities"] += 1
            continue
        changed = False
        if not school.facilities:
            pool = [
                "Perpustakaan",
                "Laboratorium komputer",
                "Laboratorium IPA",
                "Lapangan olahraga",
                "UKS",
                "Ruang multimedia",
            ]
            start = number(code + "/facilities", 0, len(pool) - 1)
            for index in range(number(code + "/facility-count", 3, 5)):
                name = pool[(start + index) % len(pool)]
                school.facilities.append(Facility(id=stable(code + "/facility/" + name), name=name))
                report["facilities"] += 1
            changed = True
        if not school.programs:
            for name, subjects in (
                ("IPA", ["Matematika", "IPA"]),
                ("IPS", ["IPS", "Bahasa Indonesia"]),
                ("Bahasa", ["Bahasa Indonesia", "Bahasa Inggris"]),
            ):
                school.programs.append(
                    Program(
                        id=stable(code + "/program/" + name),
                        name=name,
                        program_type="peminatan_sma",
                        description="SIMULASI: peminatan untuk pengujian fitur, bukan penawaran resmi sekolah.",
                        interest_profile={},
                        required_subjects=subjects,
                        tracks=[],
                        costs=[],
                    )
                )
                report["programs"] += 1
            changed = True
        for program in school.programs:
            key = code + "/" + program.name
            dimensions = (
                "realistic",
                "investigative",
                "artistic",
                "social",
                "enterprising",
                "conventional",
            )
            interest = dict(program.interest_profile or {})
            for dimension in dimensions:
                if dimension not in interest:
                    interest[dimension] = number(key + "/" + dimension, 20, 95)
                    changed = True
            program.interest_profile = interest
            academic_year = f"{year}/{year + 1}"
            if not any(cost.academic_year == academic_year for cost in program.costs):
                program.costs.append(
                    Cost(
                        id=stable(key + "/cost/" + academic_year),
                        academic_year=academic_year,
                        entrance_fee=number(key + "/entrance", 0, 20) * 250000,
                        tuition_per_period=number(key + "/monthly", 0, 4) * 50000
                        if school.ownership == "negeri"
                        else number(key + "/monthly", 4, 25) * 100000,
                        other_fee=0,
                        period_type="bulan",
                        scholarship_info="SIMULASI: biaya untuk pengujian.",
                    )
                )
                report["costs"] += 1
                changed = True
            if not program.tracks:
                for name in ("Jalur Nilai", "Jalur Prestasi"):
                    program.tracks.append(
                        AdmissionTrack(
                            id=stable(key + "/track/" + name),
                            name=name,
                            quota=number(key + "/quota/" + name, 30, 120),
                            rules={
                                "score_basis": "academic_average_0_100",
                                "supported_grades": [7, 8, 9],
                                "min_academic_score": 0,
                            },
                            history=[],
                        )
                    )
                    report["tracks"] += 1
                changed = True
            for track in program.tracks:
                for history_year in range(year - 3, year):
                    if any(item.year == history_year for item in track.history):
                        continue
                    history_key = key + "/" + track.name + f"/{history_year}"
                    minimum = number(history_key + "/min", 60, 80)
                    average = minimum + number(history_key + "/avg", 4, 10)
                    maximum = min(100, average + number(history_key + "/max", 4, 10))
                    accepted = number(history_key + "/accepted", min(20, track.quota), track.quota)
                    track.history.append(
                        AdmissionHistory(
                            id=stable(history_key),
                            year=history_year,
                            applicants=accepted + number(history_key + "/applicants", 10, 150),
                            accepted=accepted,
                            min_score=minimum,
                            avg_score=average,
                            max_score=maximum,
                            source="SIMULASI: histori buatan untuk pengujian, bukan data penerimaan resmi.",
                        )
                    )
                    report["history"] += 1
                    changed = True
        if changed:
            if MARKER not in school.data_source:
                school.data_source += "; " + MARKER
            report["schools"] += 1
    return report
