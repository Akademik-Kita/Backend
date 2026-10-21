"""Collect public school identity/location fields from Kemendikdasmen references."""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import NAMESPACE_URL, uuid5

BASE = "https://referensi.data.kemendikdasmen.go.id"


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None
        self.text = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag == "tr":
            self.row = []
        if tag in ("td", "th"):
            self.cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        if tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        if tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, value):
        if self.hidden:
            return
        self.text.append(value)
        if self.cell is not None:
            self.cell.append(value)


def fetch(url):
    request = Request(
        url, headers={"User-Agent": "AkademikKita-Catalog/2.0 (public school references)"}
    )
    with urlopen(request, timeout=30) as response:
        parser = Page()
        parser.feed(response.read().decode("utf-8"))
        return parser


def stable(key):
    return str(uuid5(NAMESPACE_URL, "https://akademikkita.local/catalog/" + key))


def school(npsn, checked_at):
    url = BASE + "/pendidikan/npsn/" + npsn
    page = fetch(url)
    fields = {}
    for row in page.rows:
        parts = [value for value in row if value and value != ":"]
        if len(parts) >= 2:
            fields[parts[0].casefold()] = parts[-1]
    text = " ".join(page.text)
    latitude = re.search(r"Lintang:\s*(-?\d+(?:\.\d+)?)", text)
    longitude = re.search(r"Bujur:\s*(-?\d+(?:\.\d+)?)", text)
    if not latitude or not longitude or fields.get("bentuk pendidikan") != "SMA":
        raise ValueError("Lokasi atau bentuk pendidikan tidak tersedia untuk " + npsn)
    lat, lon = float(latitude[1]), float(longitude[1])
    city = fields.get("kab.-kota/negara (ln)", "").upper()
    if "JAKARTA SELATAN" not in city or not (-6.5 < lat < -6.15 and 106.7 < lon < 106.95):
        raise ValueError("Identitas/koordinat sumber di luar Jakarta Selatan untuk " + npsn)
    kecamatan = re.sub(r"^KEC\.?\s+", "", fields["kecamatan/kota (ln)"], flags=re.I).title()
    website = fields.get("website")
    if not website or website == "-":
        website = None
    elif not website.startswith(("https://", "http://")):
        website = "https://" + website
    return {
        "id": stable("school/" + npsn),
        "name": fields["nama"],
        "ownership": "negeri" if fields["status sekolah"].upper() == "NEGERI" else "swasta",
        "npsn_or_code": npsn,
        "region_id": stable("city/jakarta-selatan/kecamatan/" + kecamatan),
        "address": fields["alamat"],
        "latitude": lat,
        "longitude": lon,
        "accreditation": fields.get("akreditasi", "Belum tersedia"),
        "website": website,
        "contact": fields.get("telepon") if fields.get("telepon") != "-" else None,
        "data_source": url
        + "; Ruang lingkup verifikasi: identitas, alamat, status, akreditasi dan koordinat. Program, biaya dan histori penerimaan belum tersedia dari sumber ini.",
        "last_verified_at": checked_at,
        "programs": [],
        "facilities": [],
    }, kecamatan


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/schools-jakarta-selatan.json")
    parser.add_argument("--checked-at", required=True, help="ISO timestamp of source review")
    args = parser.parse_args()
    datetime.fromisoformat(args.checked_at.replace("Z", "+00:00"))
    ids = []
    district_for = {}
    for district in ("016306", "016309", "016305"):
        page = fetch(BASE + "/pendidikan/dikmen/" + district + "/3/all/13/all")
        rows = [row for row in page.rows if len(row) >= 6 and re.fullmatch(r"\d{8}", row[1])]
        # Ambil sekolah negeri dan swasta secara konsisten per kecamatan.
        rows.sort(key=lambda row: (row[-1] != "NEGERI", row[2]))
        if len(rows) < 6:
            raise ValueError("Daftar sumber tidak memuat enam SMA pada kecamatan " + district)
        for row in rows[:10]:
            ids.append(row[1])
            district_for[row[1]] = district

    def collect(npsn):
        try:
            return school(npsn, args.checked_at)
        except ValueError as error:
            print("Skipped incomplete source:", error)
            return None

    with ThreadPoolExecutor(max_workers=4) as executor:
        collected = list(executor.map(collect, ids))
    groups = {district: [] for district in ("016306", "016309", "016305")}
    for npsn, result in zip(ids, collected):
        group = groups[district_for[npsn]]
        if result is not None and len(group) < 6:
            group.append(result)
    results = [result for group in groups.values() for result in group]
    if len(results) != 18:
        raise ValueError("Sumber belum menyediakan 18 SMA dengan koordinat lengkap")
    regions = [
        {"id": stable("province/dki-jakarta"), "name": "D.K.I. Jakarta", "type": "provinsi"},
        {
            "id": stable("city/jakarta-selatan"),
            "name": "Kota Adm. Jakarta Selatan",
            "type": "kab_kota",
            "parent_id": stable("province/dki-jakarta"),
        },
    ]
    for name in sorted({name for _, name in results}):
        regions.append(
            {
                "id": stable("city/jakarta-selatan/kecamatan/" + name),
                "name": name,
                "type": "kecamatan",
                "parent_id": stable("city/jakarta-selatan"),
            }
        )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"regions": regions, "schools": [value for value, _ in results]},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Collected {len(results)} schools with official source URLs")


if __name__ == "__main__":
    main()
