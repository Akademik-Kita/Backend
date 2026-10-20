from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from sqlalchemy import func, select, update

from app.core.config import settings
from app.demo import (
    DEMO_PROFILE_ID,
    DEMO_USER_ID,
    assessments,
    profiles,
    records,
    users,
)
from app.models import (
    AdmissionHistory,
    AdmissionTrack,
    Institution,
    Program,
    RecommendationRun,
)
from tests.conftest import SECRET


def test_school_pagination_filter_location_detail_and_compare(client, headers):
    first = client.get("/schools").json()["data"]
    second = client.get("/schools?page=2").json()["data"]
    assert len(first) == 10 and len(second) == 8
    assert len({s["id"] for s in first + second}) == 18
    assert all(s["distance_km"] is None for s in first)
    with_location = client.get("/schools", headers=headers).json()["data"]
    assert all(s["distance_km"] >= 0 for s in with_location)
    r = client.get(
        "/schools",
        params={
            "ownership": "negeri",
            "accreditation": "A",
            "kecamatan": "Kecamatan Contoh Tengah",
        },
    )
    assert r.status_code == 200
    assert all(
        s["ownership"] == "negeri"
        and s["accreditation"] == "A"
        and s["kecamatan"] == "Kecamatan Contoh Tengah"
        for s in r.json()["data"]
    )
    ids = [second[0]["id"], first[0]["id"]]
    result = client.get("/schools/compare", params={"ids": ",".join(ids)}, headers=headers)
    assert result.status_code == 200
    assert [s["id"] for s in result.json()["data"]] == ids
    school = client.get("/schools/" + ids[0]).json()["data"]
    assert school["last_verified_at"] is None
    assert "SINTETIS" in school["data_source"]
    assert len(school["jurusan"]) == 3 and len(school["fasilitas"]) == 3
    cost = school["biaya"][0]
    expected = (cost["tuition_per_period"] + cost["other_fee"]) / (
        6 if cost["period_type"] == "semester" else 1
    )
    assert cost["monthly_equivalent"] == expected


@pytest.mark.parametrize(
    "ids",
    [
        "garbage",
        "",
        str(uuid4())
        + ","
        + str(uuid4())
        + ","
        + str(uuid4())
        + ","
        + str(uuid4())
        + ","
        + str(uuid4()),
    ],
)
def test_compare_invalid_ids(client, ids):
    r = client.get("/schools/compare", params={"ids": ids})
    assert r.status_code == 422 and r.json()["data"] is None


def test_compare_duplicate_missing_and_school_not_found(client):
    school = client.get("/schools").json()["data"][0]["id"]
    assert client.get("/schools/compare", params={"ids": school + "," + school}).status_code == 422
    assert client.get("/schools/compare", params={"ids": str(uuid4())}).status_code == 404
    assert client.get("/schools/" + str(uuid4())).status_code == 404
    assert client.get("/schools?page=0").status_code == 422


def test_history_school_ownership_and_recent_years(client, db):
    school = client.get("/schools").json()["data"][0]["id"]
    program = client.get("/schools/" + school).json()["data"]["jurusan"][0]["id"]
    url = f"/schools/{school}/jurusan/{program}/riwayat-penerimaan"
    result = client.get(url)
    assert result.status_code == 200
    assert len(result.json()["data"]) == 6
    assert {h["year"] for h in result.json()["data"]} == {2023, 2024, 2025}
    other = db.scalar(select(Program).where(Program.institution_id != UUID(school)))
    assert client.get(f"/schools/{school}/jurusan/{other.id}/riwayat-penerimaan").status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"weights": {"akademik": 0.3, "minat": 0.25, "peluang": 0.2, "jarak": 0.15, "biaya": 0.1}},
    ],
)
def test_generate_matches_contract_and_latest_snapshot(client, headers, db, payload):
    result = client.post(
        "/recommendations/generate",
        headers=headers,
        **({"json": payload} if payload is not None else {}),
    )
    assert result.status_code == 200
    body = result.json()
    items = body["data"]["items"]
    assert len(items) == 45
    assert [i["rank"] for i in items] == list(range(1, len(items) + 1))
    assert [i["total_score"] for i in items] == sorted(
        [i["total_score"] for i in items], reverse=True
    )
    weights = {"akademik": 0.3, "minat": 0.25, "peluang": 0.2, "jarak": 0.15, "biaya": 0.1}
    for item in items:
        assert set(item) == {
            "school_id",
            "school_name",
            "jurusan_id",
            "jurusan_name",
            "rank",
            "total_score",
            "score_breakdown",
            "chance_low",
            "chance_high",
            "category",
            "explanation",
        }
        assert item["total_score"] == pytest.approx(
            round(sum(item["score_breakdown"][k] * weights[k] for k in weights), 2), abs=0.01
        )
        assert 0 <= item["chance_low"] <= item["chance_high"] <= 100
        assert len(item["explanation"]["positive"]) == len(item["explanation"]["negative"]) == 2
    assert client.get("/recommendations/latest", headers=headers).json() == body
    # Input dan nama sekolah boleh berubah; hasil lama harus tetap sama.
    db.execute(update(Institution).values(name="Nama Setelah Diubah"))
    db.execute(update(profiles).values(budget_max_per_bulan=0))
    db.commit()
    assert client.get("/recommendations/latest", headers=headers).json() == body
    run = db.get(RecommendationRun, UUID(body["data"]["run_id"]))
    assert run.input_snapshot["student"]["academic_average"] == 83.5
    assert run.model_version == "rule-based-v1.0"


def test_custom_weights_and_deterministic_order(client, headers):
    payload = {"weights": {"akademik": 0, "minat": 1, "peluang": 0, "jarak": 0, "biaya": 0}}
    first = client.post("/recommendations/generate", headers=headers, json=payload).json()["data"][
        "items"
    ]
    second = client.post("/recommendations/generate", headers=headers, json=payload).json()["data"][
        "items"
    ]
    assert first == second
    assert all(i["total_score"] == i["score_breakdown"]["minat"] for i in first)


def test_invalid_weights_no_saved_run(client, headers, db):
    r = client.post("/recommendations/generate", headers=headers, json={"weights": {"biaya": 0.9}})
    assert r.status_code == 422
    assert db.scalar(select(func.count()).select_from(RecommendationRun)) == 0
    assert client.get("/recommendations/latest", headers=headers).status_code == 404


def test_auth_required_expired_forged_deleted_user_and_cross_student(client, headers, db):
    assert client.post("/recommendations/generate", json={}).status_code == 401
    assert client.get("/recommendations/latest").status_code == 401
    for secret, subject, delta in [
        (SECRET, DEMO_USER_ID, -1),
        ("wrong-secret-with-minimum-thirty-two-bytes", DEMO_USER_ID, 1),
        (SECRET, uuid4(), 1),
    ]:
        token = jwt.encode(
            {"sub": str(subject), "exp": datetime.now(timezone.utc) + timedelta(hours=delta)},
            secret,
            algorithm="HS256",
        )
        assert (
            client.post(
                "/recommendations/generate", headers={"Authorization": "Bearer " + token}, json={}
            ).status_code
            == 401
        )
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 200
    other_user, other_profile = uuid4(), uuid4()
    db.execute(
        users.insert().values(
            id=other_user,
            email="other@example.invalid",
            full_name="Other",
            role="siswa",
            password_hash="unused",
        )
    )
    db.execute(
        profiles.insert().values(
            id=other_profile,
            user_id=other_user,
            grade=9,
            preferred_ownership=[],
            profile_completeness=0,
        )
    )
    db.commit()
    token = jwt.encode(
        {"sub": str(other_user), "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        SECRET,
        algorithm="HS256",
    )
    r = client.get("/recommendations/latest", headers={"Authorization": "Bearer " + token})
    assert r.status_code == 404


@pytest.mark.parametrize(
    "change", [{"latitude": None}, {"budget_max_per_bulan": None}, {"max_distance_km": None}]
)
def test_incomplete_profile_rejected(client, headers, db, change):
    db.execute(update(profiles).where(profiles.c.id == DEMO_PROFILE_ID).values(**change))
    db.commit()
    r = client.post("/recommendations/generate", headers=headers, json={})
    assert r.status_code == 409 and "Lengkapi" in r.json()["message"]


def test_zero_minat_and_missing_academic_rejected(client, headers, db):
    db.execute(
        update(assessments).values(
            scores=dict.fromkeys(
                [
                    "realistic",
                    "investigative",
                    "artistic",
                    "social",
                    "enterprising",
                    "conventional",
                ],
                0,
            )
        )
    )
    db.commit()
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409
    db.execute(records.delete())
    db.commit()
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409


def test_hard_filters_budget_zero_distance_and_ownership(client, headers, db):
    db.execute(update(profiles).values(budget_max_per_bulan=0, preferred_ownership=["negeri"]))
    db.commit()
    r = client.post("/recommendations/generate", headers=headers, json={})
    assert r.status_code == 200
    assert all(
        "Negeri" in i["school_name"] and i["score_breakdown"]["biaya"] == 100
        for i in r.json()["data"]["items"]
    )
    db.execute(update(profiles).values(max_distance_km=0.001))
    db.commit()
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409


def test_soft_filter_scores_cost_above_budget(client, headers, monkeypatch):
    monkeypatch.setenv("RECOMMENDATION_HARD_FILTERS", "false")
    settings.cache_clear()
    r = client.post("/recommendations/generate", headers=headers, json={})
    assert len(r.json()["data"]["items"]) == 54
    assert any(i["score_breakdown"]["biaya"] < 100 for i in r.json()["data"]["items"])


def test_missing_recent_history_not_fabricated(client, headers, db):
    db.execute(update(AdmissionHistory).values(year=AdmissionHistory.year - 10))
    db.commit()
    r = client.post("/recommendations/generate", headers=headers, json={})
    assert r.status_code == 409


def test_cors_allowed_origin(client):
    response = client.options(
        "/recommendations/generate",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Authorization,Content-Type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unsupported_track_not_treated_as_eligible(client, headers, db):
    db.execute(update(AdmissionTrack).values(rules={"score_basis": "zoning_only"}))
    db.commit()
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409


def test_latest_survives_invalid_current_assessment(client, headers, db):
    generated = client.post("/recommendations/generate", headers=headers, json={}).json()
    db.execute(update(assessments).values(scores={"wrong_key": 999}))
    db.commit()
    assert client.get("/recommendations/latest", headers=headers).json() == generated
    assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409


def test_partial_profile_warning_and_range_wider(client, headers, db):
    original = client.post("/recommendations/generate", headers=headers, json={}).json()["data"][
        "items"
    ]
    db.execute(update(profiles).values(profile_completeness=50))
    db.commit()
    result = client.post("/recommendations/generate", headers=headers, json={}).json()
    assert "keyakinan lebih rendah" in result["message"]
    original = {i["jurusan_id"]: i for i in original}
    for item in result["data"]["items"]:
        before = original[item["jurusan_id"]]
        assert item["chance_low"] <= before["chance_low"]
        assert item["chance_high"] >= before["chance_high"]
