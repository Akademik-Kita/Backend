from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import get_engine
from app.main import create_app
from machine_learning_recommendation_system.services.importer import import_catalog, load_catalog
from tests.conftest import ROOT


def test_registered_student_partial_profile_to_recommendation(account_db, monkeypatch):
    monkeypatch.setenv("RECOMMENDATION_HARD_FILTERS", "false")
    settings.cache_clear()
    import_catalog(account_db, load_catalog(ROOT / "data/schools-demo.json"))
    with TestClient(create_app()) as client:
        registered = client.post(
            "/auth/register",
            json={
                "email": "flow@example.invalid",
                "password": "flow-password-123",
                "full_name": "Siswa Alur",
                "role": "siswa",
            },
        )
        assert registered.status_code == 201
        login = client.post(
            "/auth/login", json={"email": "flow@example.invalid", "password": "flow-password-123"}
        )
        headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
        assert client.get("/auth/me", headers=headers).status_code == 200
        values = {
            "current_school_name": "SMP A",
            "grade": 9,
            "domisili_kecamatan": "Depok",
            "latitude": -6.385,
            "longitude": 106.825,
            "budget_max_per_bulan": 900000,
            "max_distance_km": 25,
            "preferred_ownership": ["negeri", "swasta"],
        }
        assert client.put("/profile", headers=headers, json=values).status_code == 200
        changed = client.put("/profile", headers=headers, json={"latitude": -6.386})
        assert changed.status_code == 200
        assert changed.json()["data"]["longitude"] == 106.825
        assert changed.json()["data"]["current_school_name"] == "SMP A"
        subjects = client.get("/profile/subjects").json()["data"]
        assert len(subjects) == 10
        record = client.post(
            "/profile/academic-records",
            headers=headers,
            json={"subject_id": subjects[0]["id"], "grade_level": 9, "semester": 2, "score": 85},
        )
        assert record.status_code == 201
        assert (
            client.put(
                "/profile/academic-records/" + record.json()["data"]["id"],
                headers=headers,
                json={"score": 87},
            ).status_code
            == 200
        )
        achievement = client.post(
            "/profile/achievements",
            headers=headers,
            json={"title": "Lomba", "level": "kota", "year": 2026},
        )
        assert achievement.status_code == 201
        assert len(client.get("/profile/achievements", headers=headers).json()["data"]) == 1
        assert (
            client.delete(
                "/profile/achievements/" + achievement.json()["data"]["id"], headers=headers
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/profile/interest-assessment",
                headers=headers,
                json={
                    "instrument_version": "riasec-lite-v1",
                    "scores": dict(
                        realistic=55,
                        investigative=90,
                        artistic=45,
                        social=70,
                        enterprising=60,
                        conventional=65,
                    ),
                },
            ).status_code
            == 201
        )
        response = client.post("/recommendations/generate", headers=headers, json={})
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["items"]) == 54
        assert any(item["score_breakdown"]["biaya"] < 100 for item in data["items"])
        assert client.get("/recommendations/latest", headers=headers).json()["data"] == data
        assert client.put("/profile", headers=headers, json={"longitude": None}).status_code == 200
        assert client.post("/recommendations/generate", headers=headers, json={}).status_code == 409
        assert client.get("/recommendations/latest", headers=headers).json()["data"] == data
    get_engine().dispose()


def test_default_config_uses_cost_and_distance_penalties(monkeypatch):
    monkeypatch.delenv("RECOMMENDATION_HARD_FILTERS", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("AKADEMIKKITA_ENV_FILE", str(ROOT / "nonexistent-test.env"))
    settings.cache_clear()
    assert settings().hard_filters is False
    settings.cache_clear()
