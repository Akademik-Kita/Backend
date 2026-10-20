# AkademikKita Backend

Satu backend FastAPI untuk akun, profil siswa, katalog SMA, dan rekomendasi berbasis aturan. Endpoint mengikuti kontrak frontend; struktur proyek dibagi berdasarkan fitur.

## Menjalankan backend

```powershell
cd "C:\Users\Haikal\Documents\Akademik Kita\akademikkita-backend"
py setup.py
.\.venv\Scripts\python.exe -m app.cli migrate
.\.venv\Scripts\python.exe -m app.cli db-check
.\run.ps1
```

Swagger: <http://127.0.0.1:8000/docs>. Konfigurasi PostgreSQL ada di `.env`. Untuk setup baru, salin `.env.supabase.example` menjadi `.env`, lalu isi URI database dan secret JWT acak minimal 32 byte.

## Struktur

```text
crud_database/    model, schema, keamanan dan router akun/profil siswa
machine_learning_recommendation_system/
  models/         sekolah dan hasil rekomendasi
  schemas/        kontrak sekolah dan rekomendasi
  routers/        schools dan recommendations
  services/       katalog, importer, scoring dan input siswa
app/
  core/           konfigurasi, koneksi database dan error
  models/         metadata SQLAlchemy bersama
  schemas/        envelope dan ekspor kontrak bersama
  main.py         satu aplikasi FastAPI
  cli.py          migrasi, pemeriksaan database, impor, demo
migrations/       satu riwayat migrasi
data/             katalog sekolah resmi dan data demo
docs/             kontrak API, algoritma, sumber data
tests/            pengujian fitur dan integrasi
```

`python -m app.cli migrate` menangani seluruh tabel. Untuk database lama yang sudah lengkap, migrasi menyandingkan skema dan mengadopsinya tanpa membuat ulang akun/profil/sekolah. Penanda revisi lama tetap disimpan untuk kompatibilitas; seluruh pekerjaan berikutnya memakai `alembic.ini` dan riwayat migrasi tunggal.

## Data sekolah

Katalog `data/schools-jakarta-selatan.json` memuat 18 SMA nyata, dengan identitas, NPSN, alamat, status, akreditasi, dan koordinat dari Kemendikdasmen. Sumber dan lingkup verifikasi dicantumkan per sekolah. Impor ulang memakai UUID stabil dan tidak menduplikasi data:

```powershell
.\.venv\Scripts\python.exe -m app.cli validate data\schools-jakarta-selatan.json
.\.venv\Scripts\python.exe -m app.cli import data\schools-jakarta-selatan.json
```

Program, fasilitas, biaya, serta histori penerimaan yang belum bersumber dikembalikan sebagai daftar kosong. Sekolah tersebut tersedia di daftar/detail/perbandingan, tetapi belum menjadi kandidat rekomendasi. `last_verified_at` menyatakan pemeriksaan identitas/lokasi; bukan verifikasi seluruh data seleksi. 

## Demo lengkap

```powershell
.\run-demo.ps1
```

Demo berjalan pada port **8001**, memakai `.env.demo` dan SQLite lokal terpisah. Script menyiapkan seluruh skema asli, sepuluh mapel, satu akun siswa, nilai, RIASEC, dan 18 sekolah sintetis. Login lewat `/auth/login` memakai email `siswa@example.invalid` dan password `demo-akademikkita-123`. Profil siswa dapat diubah lewat endpoint yang sama dengan backend utama.

Swagger demo: <http://127.0.0.1:8001/docs>. Data sintetis diberi label dalam hasil rekomendasi. `demo-init` menolak PostgreSQL, dan importer CLI menolak katalog sintetis saat `DEMO_MODE=false`.

## API

- Seluruh sukses/error memakai envelope `success`, `data`, `message`.
- `/schools` dan `/profile/subjects` publik; lokasi siswa pada katalog menggunakan token opsional.
- Profil menerima partial update, termasuk satu koordinat. Kelengkapan lokasi membutuhkan kedua koordinat; generate menolak lokasi yang belum lengkap.
- Default `RECOMMENDATION_HARD_FILTERS=false`: biaya/jarak di atas preferensi tetap dinilai dengan penalti. Filter kepemilikan dan kelayakan jalur tetap berlaku.
- Lima bobot harus berada pada 0–1 dengan total 1. Skor faktor dan total berada pada 0–100.
- Histori memakai tiga tahun kalender selesai terakhir. Data biaya/histori yang tidak tersedia tidak diubah menjadi angka perkiraan.
- Hasil latest merupakan snapshot milik akun tersebut. Peluang merupakan heuristik, bukan probabilitas terkalibrasi.

Daftar kontrak: [API.md](docs/API.md). OpenAPI tersedia di `/openapi.json` dan `docs/openapi.json`.

## Pengujian

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Tes otomatis memakai SQLite sementara dan mengabaikan `.env` aplikasi. Konfigurasi `TEST_DATABASE_URL` eksternal ditolak sebelum koneksi. Pemeriksaan PostgreSQL operasional dilakukan terpisah melalui `db-check`.
