import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from machine_learning_recommendation_system.services.importer import load_catalog
from scripts.fetch_school_catalog import Builder


class CollectionTests(unittest.TestCase):
    def test_validated_identity_deduplication_and_region_hierarchy(self):
        builder = Builder()
        row = {
            "npsn": "20101301",
            "nama": "SMAS REGINA PACIS",
            "bentuk_pendidikan": "SMA",
            "status_sekolah": "SWASTA",
            "provinsi": "Prov. D.K.I. Jakarta",
            "kabupaten": "Kota Adm. Jakarta Barat",
            "kecamatan": "Kec. Palmerah",
            "sekolah_id": "10812100-555C-4F8E-A132-FFBCF1C12F15",
            "lintang": -6.20,
            "bujur": 106.80,
            "alamat_jalan": "JL. PALMERAH UTARA I",
            "akreditasi": "A",
        }
        at = datetime.now(timezone.utc)
        builder.add(row, at, "D.K.I. Jakarta")
        builder.add(row, at, "D.K.I. Jakarta")
        for code, changes in (
            ("99999991", {"bentuk_pendidikan": "SMK"}),
            ("99999992", {"lintang": float("nan")}),
            ("99999993", {"provinsi": "Prov. Papua"}),
            ("99999994", {"alamat_jalan": ""}),
        ):
            builder.add({**row, "npsn": code, **changes}, at, "D.K.I. Jakarta")
        self.assertEqual(len(builder.schools), 1)
        self.assertEqual(len(builder.skipped), 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            builder.save(path)
            catalog = load_catalog(path)
        self.assertEqual(len(catalog.regions), 3)
        school = catalog.schools[0]
        self.assertEqual(school.npsn_or_code, row["npsn"])
        self.assertEqual(school.name, row["nama"])
        self.assertEqual(school.programs, [])
        self.assertEqual(school.facilities, [])
        self.assertTrue(school.data_source.startswith("https://sekolah.data.kemendikdasmen.go.id/"))
