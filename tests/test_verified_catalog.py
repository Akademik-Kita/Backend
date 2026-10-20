from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.main import create_app
from app.models import Institution, Program
from machine_learning_recommendation_system.services.importer import import_catalog, load_catalog
from tests.conftest import ROOT


def test_official_catalog_import_is_repeatable_without_fabricated_programs(account_db):
    catalog = load_catalog(ROOT / "data/schools-jakarta-selatan.json")
    assert len(catalog.schools) == 18
    assert all(
        "referensi.data.kemendikdasmen.go.id" in school.data_source for school in catalog.schools
    )
    assert all(not school.programs for school in catalog.schools)
    import_catalog(account_db, catalog)
    import_catalog(account_db, catalog)
    assert account_db.scalar(select(func.count()).select_from(Institution)) == 18
    assert account_db.scalar(select(func.count()).select_from(Program)) == 0
    with TestClient(create_app()) as client:
        first = client.get("/schools").json()["data"]
        second = client.get("/schools?page=2").json()["data"]
        assert len(first + second) == 18
        assert all(not school["jurusan_tersedia"] for school in first + second)
        ids = ",".join(school["id"] for school in first[:4])
        compare = client.get("/schools/compare", params={"ids": ids})
        assert compare.status_code == 200
        assert all(
            not school["biaya"] and not school["jurusan"] for school in compare.json()["data"]
        )
