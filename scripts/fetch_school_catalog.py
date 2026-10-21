"""Collect public SMA map records; costs and admissions are filled separately."""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.robotparser import RobotFileParser
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from machine_learning_recommendation_system.services.importer import (  # noqa: E402
    CatalogInput,
    RegionInput,
    SchoolInput,
)

ORIGIN = "https://sekolah.data.kemendikdasmen.go.id"
MAP = "/v1/sekolah-service/sekolah/cari-sekolah-by-location"
AGENT = "AkademikKita-Catalog/3.0 (+https://github.com/Akademik-Kita)"
CENTERS = [
    ("Jakarta", -6.20, 106.82, "D.K.I. Jakarta|Jawa Barat|Banten"),
    ("Bekasi", -6.24, 106.99, "Jawa Barat|D.K.I. Jakarta"),
    ("Depok", -6.39, 106.82, "Jawa Barat|Banten"),
    ("Bogor", -6.60, 106.80, "Jawa Barat"),
    ("Tangerang", -6.18, 106.63, "Banten|D.K.I. Jakarta"),
    ("Bandung", -6.92, 107.62, "Jawa Barat"),
    ("Surabaya", -7.26, 112.75, "Jawa Timur"),
    ("Medan", 3.59, 98.67, "Sumatera Utara"),
    ("Semarang", -6.99, 110.42, "Jawa Tengah"),
    ("Yogyakarta", -7.80, 110.37, "D.I. Yogyakarta|Jawa Tengah"),
    ("Malang", -7.98, 112.63, "Jawa Timur"),
    ("Surakarta", -7.57, 110.82, "Jawa Tengah"),
    ("Makassar", -5.15, 119.43, "Sulawesi Selatan"),
    ("Palembang", -2.99, 104.76, "Sumatera Selatan"),
    ("Padang", -0.95, 100.35, "Sumatera Barat"),
    ("Pekanbaru", 0.51, 101.45, "Riau"),
    ("Bandar Lampung", -5.43, 105.26, "Lampung"),
    ("Serang", -6.12, 106.15, "Banten"),
    ("Denpasar", -8.65, 115.22, "Bali"),
    ("Banjarmasin", -3.32, 114.59, "Kalimantan Selatan"),
    ("Pontianak", -0.03, 109.34, "Kalimantan Barat"),
    ("Samarinda", -0.50, 117.15, "Kalimantan Timur"),
    ("Balikpapan", -1.24, 116.85, "Kalimantan Timur"),
    ("Manado", 1.47, 124.84, "Sulawesi Utara"),
    ("Palu", -0.90, 119.87, "Sulawesi Tengah"),
    ("Kendari", -3.99, 122.52, "Sulawesi Tenggara"),
    ("Banda Aceh", 5.55, 95.32, "Aceh"),
    ("Jambi", -1.61, 103.61, "Jambi"),
    ("Bengkulu", -3.80, 102.27, "Bengkulu"),
    ("Pangkalpinang", -2.13, 106.11, "Kepulauan Bangka Belitung"),
    ("Batam", 1.13, 104.05, "Kepulauan Riau"),
    ("Tanjungpinang", 0.92, 104.45, "Kepulauan Riau"),
    ("Palangka Raya", -2.21, 113.92, "Kalimantan Tengah"),
    ("Tarakan", 3.30, 117.63, "Kalimantan Utara"),
    ("Gorontalo", 0.54, 123.06, "Gorontalo"),
    ("Mamuju", -2.68, 118.89, "Sulawesi Barat"),
    ("Mataram", -8.58, 116.12, "Nusa Tenggara Barat"),
    ("Kupang", -10.17, 123.61, "Nusa Tenggara Timur"),
    ("Ambon", -3.69, 128.18, "Maluku"),
    ("Ternate", 0.79, 127.38, "Maluku Utara"),
    ("Jayapura", -2.54, 140.72, "Papua"),
    ("Sorong", -0.88, 131.25, "Papua Barat Daya|Papua Barat"),
    ("Manokwari", -0.86, 134.06, "Papua Barat"),
    ("Merauke", -8.49, 140.40, "Papua Selatan|Papua"),
    ("Timika", -4.55, 136.89, "Papua Tengah|Papua"),
    ("Wamena", -4.10, 138.94, "Papua Pegunungan|Papua"),
    ("Cirebon", -6.71, 108.56, "Jawa Barat"),
    ("Tasikmalaya", -7.33, 108.22, "Jawa Barat"),
    ("Purwokerto", -7.42, 109.24, "Jawa Tengah"),
    ("Kediri", -7.82, 112.02, "Jawa Timur"),
    ("Jember", -8.17, 113.70, "Jawa Timur"),
    ("Madiun", -7.63, 111.52, "Jawa Timur"),
    ("Pematangsiantar", 2.96, 99.06, "Sumatera Utara"),
    ("Sukabumi", -6.92, 106.93, "Jawa Barat"),
    ("Pekalongan", -6.89, 109.68, "Jawa Tengah"),
    ("Tegal", -6.87, 109.14, "Jawa Tengah"),
]
HTTP = r"""
$ErrorActionPreference = 'Stop'
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$q = [Console]::In.ReadToEnd() | ConvertFrom-Json
try {
    $p = @{Uri=$q.url;Method=$q.method;TimeoutSec=20;UseBasicParsing=$true;MaximumRedirection=0;UserAgent=$q.agent;ContentType='application/json; charset=utf-8'}
    if ($q.body) { $p.Body = [Text.Encoding]::UTF8.GetBytes($q.body) }
    $r = Invoke-WebRequest @p
    @{status=[int]$r.StatusCode;body=[string]$r.Content} | ConvertTo-Json -Compress
} catch {
    @{status=$(if ($_.Exception.Response) {[int]$_.Exception.Response.StatusCode} else {0})} | ConvertTo-Json -Compress
}
"""


def normalized(value):
    return re.sub(
        r"[^\w]", "", re.sub(r"^(prov\.?|kec\.?)\s+", "", str(value or ""), flags=re.I).casefold()
    )


def stable(key):
    return uuid5(NAMESPACE_URL, "https://akademikkita.local/catalog/" + key)


class Source:
    def __init__(self):
        self.last = 0
        self.cache = ROOT / ".cache/school-expansion"
        self.cache.mkdir(parents=True, exist_ok=True)
        self.requests = 0
        self.cache_hits = 0
        raw = self.wire("/robots.txt")
        self.robots = RobotFileParser()
        self.robots.parse([] if raw.lstrip().startswith("<") else raw.splitlines())
        self.delay = max(1, self.robots.crawl_delay(AGENT) or 0)

    def wire(self, path, body=None):
        if path not in ("/robots.txt", MAP):
            raise ValueError("Unsupported source endpoint")
        time.sleep(max(0, getattr(self, "delay", 1) - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", HTTP],
            input=json.dumps(
                {
                    "url": ORIGIN + path,
                    "body": json.dumps(body) if body else None,
                    "method": "POST" if body else "GET",
                    "agent": AGENT,
                }
            ),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        value = json.loads(result.stdout)
        self.requests += 1
        if path == "/robots.txt" and value.get("status") in (404, 410):
            return ""
        if result.returncode or value.get("status") != 200:
            raise RuntimeError(
                f"Sumber menolak/gagal HTTP {value.get('status', 0)}; pengambilan dihentikan"
            )
        raw = value["body"]
        if len(raw.encode()) > 5 * 1024 * 1024:
            raise RuntimeError("Respons sumber terlalu besar")
        return raw

    def map(self, lat, lon):
        if not self.robots.can_fetch(AGENT, ORIGIN + MAP):
            raise RuntimeError("robots.txt melarang pengambilan")
        body = {
            "keyword": "",
            "bentuk_pendidikan": "SMA",
            "status_sekolah": "",
            "lintang": lat,
            "bujur": lon,
            "use_geo_kabupaten_kota": False,
        }
        cache = self.cache / (
            hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest() + ".json"
        )
        if cache.exists():
            document = json.loads(cache.read_text(encoding="utf-8"))
            if (
                datetime.now(timezone.utc) - datetime.fromisoformat(document["at"])
            ).total_seconds() < 86400:
                self.cache_hits += 1
                return document["data"], datetime.fromisoformat(document["at"])
        try:
            value = json.loads(self.wire(MAP, body))
        except ValueError:
            raise RuntimeError("Sumber meminta verifikasi atau tidak mengirim JSON") from None
        if value.get("status_code") != 200 or not isinstance(value.get("data"), list):
            raise RuntimeError("Format sumber berubah")
        at = datetime.now(timezone.utc)
        cache.write_text(
            json.dumps({"at": at.isoformat(), "data": value["data"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        return value["data"], at


class Builder:
    def __init__(self):
        self.regions = {}
        self.schools = {}
        self.skipped = {}

    def add(self, row, at, allowed):
        code = str(row.get("npsn") or "")
        if code in self.schools:
            return
        try:
            if not re.fullmatch(r"\d{8}", code) or row.get("bentuk_pendidikan") != "SMA":
                raise ValueError("NPSN atau bentuk pendidikan tidak sesuai")
            if normalized(row.get("provinsi")) not in {
                normalized(name) for name in allowed.split("|")
            }:
                raise ValueError("Wilayah dan posisi peta tidak konsisten")
            source_id = str(UUID(row["sekolah_id"])).upper()
            lat, lon = float(row["lintang"]), float(row["bujur"])
            if not all(map(math.isfinite, (lat, lon))) or not (
                -11.5 <= lat <= 6.5 and 94 <= lon <= 142.5
            ):
                raise ValueError("Koordinat tidak valid")
            if not str(row.get("alamat_jalan") or "").strip():
                raise ValueError("Alamat belum tersedia")
            parent = None
            for field, kind in (
                ("provinsi", "provinsi"),
                ("kabupaten", "kab_kota"),
                ("kecamatan", "kecamatan"),
            ):
                name = re.sub(
                    r"^(Prov\.?|Kec\.?)\s+", "", str(row.get(field) or "").strip(), flags=re.I
                )
                if not name:
                    raise ValueError("Wilayah belum lengkap")
                region_id = stable(f"region/{kind}/{parent}/{normalized(name)}")
                self.regions[region_id] = RegionInput(
                    id=region_id, name=name, type=kind, parent_id=parent
                )
                parent = region_id
            accreditation = str(row.get("akreditasi") or "Belum tersedia").strip()
            if len(accreditation) > 20:
                raise ValueError("Akreditasi tidak valid")
            self.schools[code] = SchoolInput(
                id=stable("school/" + code),
                name=row["nama"].strip(),
                ownership=row["status_sekolah"].lower(),
                npsn_or_code=code,
                region_id=parent,
                address=row["alamat_jalan"].strip(),
                latitude=lat,
                longitude=lon,
                accreditation=accreditation,
                facilities=[],
                last_verified_at=at,
                data_source=f"{ORIGIN}/profil-sekolah/{source_id}; Identitas, alamat, status, akreditasi dan koordinat dari peta publik Sekolah Kita. Metadata biaya, program, fasilitas dan histori diisi terpisah sebagai simulasi.",
            )
        except (ValueError, TypeError, KeyError) as error:
            self.skipped[code or row.get("nama", "unknown")] = str(error)

    def save(self, path):
        used = {school.region_id for school in self.schools.values()}
        for _ in range(3):
            used |= {
                self.regions[key].parent_id for key in list(used) if self.regions[key].parent_id
            }
        catalog = CatalogInput(
            regions=[region for key, region in self.regions.items() if key in used],
            schools=list(self.schools.values()),
        )
        temporary = path.with_suffix(".tmp")
        temporary.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=3000)
    parser.add_argument("--output", type=Path, default=ROOT / "data/schools-expanded.json")
    args = parser.parse_args()
    if not 1 <= args.limit <= 10000:
        parser.error("limit harus 1–10000")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source, builder = Source(), Builder()
    offsets = [
        (0, 0),
        (0.055, 0),
        (-0.055, 0),
        (0, 0.055),
        (0, -0.055),
        (0.055, 0.055),
        (-0.055, -0.055),
        (0.055, -0.055),
        (-0.055, 0.055),
    ]
    queries = 0
    try:
        for delta_lat, delta_lon in offsets:
            for name, lat, lon, allowed in CENTERS:
                rows, at = source.map(round(lat + delta_lat, 5), round(lon + delta_lon, 5))
                for row in rows:
                    if len(builder.schools) >= args.limit:
                        break
                    builder.add(row, at, allowed)
                queries += 1
                if queries % 10 == 0 or len(builder.schools) >= args.limit:
                    builder.save(args.output)
                    print(
                        f"{queries} pencarian; {len(builder.schools)} SMA valid; terakhir {name}",
                        flush=True,
                    )
                if len(builder.schools) >= args.limit:
                    return
    finally:
        builder.save(args.output)
        args.output.with_suffix(".report.json").write_text(
            json.dumps(
                {
                    "source": ORIGIN,
                    "collected": len(builder.schools),
                    "queries": queries,
                    "network_requests": source.requests,
                    "cache_hits": source.cache_hits,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "excluded": builder.skipped,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
