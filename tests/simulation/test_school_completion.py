import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import install_error_handlers
from app.demo import DEMO_EMAIL, DEMO_PASSWORD, seed_demo_student
from app.models import AdmissionHistory, Base, Institution, Program, Region
from crud_database.routers import auth, profile
from machine_learning_recommendation_system.routers import recommendations, schools
from machine_learning_recommendation_system.services.importer import (
    append_catalog,
    import_catalog,
    load_catalog,
)
from machine_learning_recommendation_system.services.simulation import complete_school_data

ROOT = Path(__file__).resolve().parents[2]


class CompletionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(
            os.environ,
            {
                "DEMO_MODE": "true",
                "JWT_SECRET_KEY": "test-only-school-completion-secret-long-enough",
                "AKADEMIKKITA_ENV_FILE": str(Path(self.directory.name) / "no-env-file"),
            },
        )
        self.env.start()
        settings.cache_clear()
        self.engine = create_engine("sqlite:///" + str(Path(self.directory.name) / "test.db"))

        @event.listens_for(self.engine, "connect")
        def foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        Base.metadata.create_all(self.engine)
        catalog = load_catalog(ROOT / "data/schools-jakarta-selatan.json")
        self.catalog = catalog.model_copy(update={"schools": catalog.schools[:2]})
        with Session(self.engine) as db:
            import_catalog(db, self.catalog)
            seed_demo_student(db)
        app = FastAPI()
        for router in (auth.router, profile.router, schools.router, recommendations.router):
            app.include_router(router, prefix="/api")
        install_error_handlers(app)

        def local_db():
            with Session(self.engine) as db:
                yield db

        app.dependency_overrides[get_db] = local_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.env.stop()
        settings.cache_clear()
        self.directory.cleanup()

    def complete(self):
        with Session(self.engine) as db:
            with db.no_autoflush:
                result = complete_school_data(db, 2026)
            db.commit()
            return result

    def test_stable_completion_keeps_identity_and_existing_values(self):
        report = self.complete()
        self.assertEqual((report["schools"], report["programs"], report["history"]), (2, 6, 36))
        with Session(self.engine) as db:
            program = db.scalar(select(Program))
            program.description = "Deskripsi yang telah dikurasi"
            db.commit()
            identity = [
                (school.id, school.name, school.npsn_or_code, school.latitude, school.longitude)
                for school in db.scalars(select(Institution))
            ]
            history = [
                (row.id, row.min_score, row.avg_score, row.max_score)
                for row in db.scalars(select(AdmissionHistory).order_by(AdmissionHistory.id))
            ]
        self.assertEqual(self.complete()["schools"], 0)
        with Session(self.engine) as db:
            self.assertEqual(
                identity,
                [
                    (school.id, school.name, school.npsn_or_code, school.latitude, school.longitude)
                    for school in db.scalars(select(Institution))
                ],
            )
            self.assertEqual(
                history,
                [
                    (row.id, row.min_score, row.avg_score, row.max_score)
                    for row in db.scalars(select(AdmissionHistory).order_by(AdmissionHistory.id))
                ],
            )
            self.assertIn(
                "Deskripsi yang telah dikurasi", db.scalars(select(Program.description)).all()
            )

    def test_preview_rolls_back_and_invalid_year_is_rejected(self):
        with Session(self.engine) as db:
            with db.no_autoflush:
                self.assertEqual(complete_school_data(db, 2026)["schools"], 2)
            db.rollback()
            self.assertEqual(db.scalar(select(func.count()).select_from(Program)), 0)
            with self.assertRaises(ValueError):
                complete_school_data(db, 2200)

    def test_append_preserves_existing_school_and_batch_completion(self):
        with Session(self.engine) as db:
            original = db.get(Institution, self.catalog.schools[0].id)
            original.name = "Nama yang sudah dikurasi"
            db.commit()
            expanded = load_catalog(ROOT / "data/schools-jakarta-selatan.json")
            expanded.schools = expanded.schools[:3]
            added = append_catalog(db, expanded)
            self.assertEqual(added, [expanded.schools[2].id])
            with db.no_autoflush:
                report = complete_school_data(db, 2026, school_ids=added)
            db.commit()
            self.assertEqual(report["schools"], 1)
            self.assertEqual(db.scalar(select(func.count()).select_from(Program)), 3)
            self.assertEqual(db.get(Institution, original.id).name, "Nama yang sudah dikurasi")
            self.assertEqual(append_catalog(db, expanded), [])
            self.assertEqual(db.scalar(select(func.count()).select_from(Institution)), 3)

    def test_school_and_recommendation_features_use_completed_database(self):
        self.complete()
        login = self.client.post(
            "/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
        )
        self.assertEqual(login.status_code, 200, login.text)
        headers = {"Authorization": "Bearer " + login.json()["data"]["access_token"]}
        for path in (
            "/api/auth/me",
            "/api/profile",
            "/api/profile/subjects",
            "/api/profile/academic-records",
            "/api/profile/interest-assessment/latest",
        ):
            response = self.client.get(path, headers=headers)
            self.assertEqual(response.status_code, 200, response.text)
        response = self.client.get("/api/schools")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(all(school["data_is_simulated"] for school in response.json()["data"]))
        ids = [str(school.id) for school in self.catalog.schools]
        detail = self.client.get("/api/schools/" + ids[0])
        self.assertEqual(detail.status_code, 200, detail.text)
        school = detail.json()["data"]
        self.assertEqual(len(school["jurusan"]), 3)
        self.assertEqual(len(school["biaya"]), 3)
        self.assertGreaterEqual(len(school["fasilitas"]), 3)
        compared = self.client.get("/api/schools/compare", params={"ids": ",".join(ids)})
        self.assertEqual(compared.status_code, 200, compared.text)
        history = self.client.get(
            f"/api/schools/{ids[0]}/jurusan/{school['jurusan'][0]['id']}/riwayat-penerimaan"
        )
        self.assertEqual(history.status_code, 200, history.text)
        self.assertEqual(len(history.json()["data"]), 6)
        for row in history.json()["data"]:
            self.assertLessEqual(row["accepted"], row["applicants"])
            self.assertLessEqual(row["accepted"], row["quota"])
            self.assertTrue(row["source"].startswith("SIMULASI:"))
        generated = self.client.post("/api/recommendations/generate", headers=headers, json={})
        self.assertEqual(generated.status_code, 200, generated.text)
        data = generated.json()["data"]
        self.assertEqual(len(data["recommendations"]), 2)
        for rank, item in enumerate(data["recommendations"], 1):
            self.assertEqual(item["rank"], rank)
            self.assertTrue(item["data_is_simulated"])
            self.assertEqual(len(item["score_breakdown"]), 5)
            self.assertGreater(len(item["explanation"]["positive"]), 0)
            self.assertLessEqual(item["chance_low"], item["chance_high"])
        latest = self.client.get("/api/recommendations/latest", headers=headers)
        self.assertEqual(latest.status_code, 200, latest.text)
        self.assertEqual(latest.json()["data"], data)

    def test_search_matches_city_and_keeps_other_provinces_out_across_pages(self):
        with Session(self.engine) as db:
            districts = []
            for province, city, district in (
                ("Jawa Barat", "Kota Cirebon", "Harjamukti"),
                ("Lampung", "Kota Metro", "Metro Pusat"),
            ):
                parent = None
                for name, kind in (
                    (province, "provinsi"),
                    (city, "kab_kota"),
                    (district, "kecamatan"),
                ):
                    region = Region(id=uuid4(), name=name, type=kind, parent_id=parent)
                    db.add(region)
                    db.flush()
                    parent = region.id
                districts.append(parent)
            template = self.catalog.schools[0].model_dump(exclude={"programs", "facilities"})
            cirebon_ids = set()
            for index in range(12):
                identifier = uuid4()
                is_cirebon = index < 11
                if is_cirebon:
                    cirebon_ids.add(str(identifier))
                db.add(
                    Institution(
                        **{
                            **template,
                            "id": identifier,
                            "name": f"SMA Harapan {index}",
                            "npsn_or_code": f"990000{index:02d}",
                            "data_source": "Test fixture",
                            "region_id": districts[0 if is_cirebon else 1],
                        }
                    )
                )
            db.commit()
        first = self.client.get("/api/schools", params={"search": "  CiReBoN  "}).json()["data"]
        second = self.client.get("/api/schools", params={"search": "Cirebon", "page": 2}).json()[
            "data"
        ]
        self.assertEqual((len(first), len(second)), (10, 1))
        self.assertEqual({row["id"] for row in first + second}, cirebon_ids)
        self.assertTrue(all(row["kecamatan"] == "Harjamukti" for row in first + second))
        for keyword in ("Lampung", "Metro", "99000011"):
            data = self.client.get("/api/schools", params={"search": keyword}).json()["data"]
            self.assertEqual([row["name"] for row in data], ["SMA Harapan 11"])
        for keyword in ("%", "_", "wilayah-tidak-ada"):
            response = self.client.get("/api/schools", params={"search": keyword})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"], [])
        response = self.client.get(
            "/api/schools", params={"search": "Cirebon", "kecamatan": "Metro Pusat"}
        )
        self.assertEqual(response.json()["data"], [])
