from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import Institution
from machine_learning_recommendation_system.services.importer import (
    CatalogInput,
    import_catalog,
    load_catalog,
)
from tests.conftest import ROOT


def test_idempotent_import_and_update(db):
    catalog = load_catalog(ROOT / "data" / "schools-demo.json")
    import_catalog(db, catalog)
    assert db.scalar(select(func.count()).select_from(Institution)) == 18
    changed = catalog.model_copy(deep=True)
    changed.schools[0].address = "Alamat diperbarui"
    import_catalog(db, changed)
    assert db.get(Institution, changed.schools[0].id).address == "Alamat diperbarui"
    assert db.scalar(select(func.count()).select_from(Institution)) == 18


@pytest.mark.parametrize(
    "kind",
    [
        "range",
        "history_order",
        "count",
        "duplicate",
        "unknown_rules",
        "bad_year",
        "region_cycle",
        "interest_zero",
    ],
)
def test_invalid_catalog_rejected_before_database(kind):
    catalog = load_catalog(ROOT / "data" / "schools-demo.json").model_dump(mode="json")
    catalog = deepcopy(catalog)
    school = catalog["schools"][0]
    if kind == "range":
        school["latitude"] = 100
    elif kind == "history_order":
        school["programs"][0]["tracks"][0]["history"][0]["min_score"] = 100
    elif kind == "count":
        school["programs"][0]["tracks"][0]["history"][0]["accepted"] = 99999
    elif kind == "duplicate":
        catalog["schools"][1]["id"] = school["id"]
    elif kind == "unknown_rules":
        school["programs"][0]["tracks"][0]["rules"]["unhandled_zoning_rule"] = True
    elif kind == "bad_year":
        school["programs"][0]["costs"][0]["academic_year"] = "2026/2029"
    elif kind == "region_cycle":
        catalog["regions"][0]["parent_id"] = catalog["regions"][0]["id"]
    else:
        school["programs"][0]["interest_profile"] = dict.fromkeys(
            school["programs"][0]["interest_profile"], 0
        )
    with pytest.raises(ValidationError):
        CatalogInput.model_validate(catalog)


def test_import_rollback_on_reparent_conflict(db):
    catalog = load_catalog(ROOT / "data" / "schools-demo.json").model_copy(deep=True)
    original = db.get(Institution, catalog.schools[0].id).address
    catalog.schools[0].address = "Perubahan ini harus rollback"
    catalog.schools[1].programs[0].id = catalog.schools[0].programs[0].id
    with pytest.raises(ValueError, match="induk lain"):
        import_catalog(db, catalog)
    db.expire_all()
    assert db.get(Institution, catalog.schools[0].id).address == original
