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

`last_verified_at` menyatakan pemeriksaan identitas/lokasi; bukan verifikasi seluruh data seleksi. Metadata yang dilengkapi secara acak diberi label simulasi seperti dijelaskan di bawah.

## Katalog SMA nasional

`data/schools-expanded.json` berisi 3.000 identitas SMA unik dari endpoint peta publik [Sekolah Kita Kemendikdasmen](https://sekolah.data.kemendikdasmen.go.id/sekolah), diambil pada 21 Oktober 2026. Data mencakup wilayah sekitar 56 kota; belum seluruh SMA Indonesia. NPSN, nama, alamat, status, akreditasi, dan koordinat mengikuti sumber. Respons dengan identitas/koordinat tidak valid atau provinsi yang tidak sesuai area pencarian dikeluarkan. Ringkasan pengambilan tersedia di `data/schools-expanded.report.json`.

```powershell
# Pengambilan ulang di Windows: cache 24 jam, jeda minimal 1 detik per permintaan
.\.venv\Scripts\python.exe scripts\fetch_school_catalog.py --limit 3000
.\.venv\Scripts\python.exe -m app.cli validate data\schools-expanded.json
# Tambah identitas yang belum ada berdasarkan NPSN dan lengkapi dengan simulasi
.\.venv\Scripts\python.exe -m app.cli append data\schools-expanded.json
```

`append` mempertahankan data sekolah yang sudah ada dan menyimpan seluruh penambahan dalam satu transaksi. Ambil cadangan sebelum menjalankannya pada database lain. Pengambil berhenti saat sumber menolak permintaan; tidak melewati CAPTCHA. Batas `--limit` adalah maksimum pengambilan dari area yang dikonfigurasi, bukan jaminan jumlah tersedia.

Sesudah perluasan, Supabase memuat 3.002 sekolah, 9.006 program/biaya, dan 54.036 histori; SQLite lokal memuat 3.049 sekolah, 9.147 program/biaya, dan 54.882 histori. Selisih berasal dari katalog lama yang tetap dipertahankan. Semua sekolah memiliki program, biaya, fasilitas, jalur, dan histori. Penambahan ulang katalog diuji tidak menduplikasi data. Cadangan tersimpan di `.audit-backup/`; akun, profil, nilai, minat, dan RLS diverifikasi tidak berubah.

Daftar sekolah menggunakan 10 hasil per halaman, dengan tombol sebelumnya/berikutnya di halaman Bandingkan SMA. Pencarian nama, NPSN, atau wilayah diperbarui otomatis setelah 300 ms; perubahan filter mengembalikan halaman ke awal dan respons pencarian lama diabaikan. Pencarian kota/kabupaten dan provinsi mencakup sekolah di wilayah turunannya. Rekomendasi menghitung seluruh kandidat dan mengembalikan 50 hasil teratas supaya respons dan tampilan tetap terbatas.

## Pelengkapan data simulasi

Identitas sekolah tetap mengikuti katalog yang tersimpan. Data yang belum tersedia dapat dilengkapi dengan simulasi konsisten berdasarkan NPSN: tiga peminatan, biaya tahun berjalan, fasilitas, dua jalur seleksi, dan histori tiga tahun selesai terakhir. Nilai tersimpan, tidak berubah saat refresh, dan data yang sudah ada dipertahankan.

```powershell
# Lihat rencana perubahan pada database aktif
.\.venv\Scripts\python.exe -m app.cli complete-school-data
# Simpan perubahan
.\.venv\Scripts\python.exe -m app.cli complete-school-data --apply
```

Perintah memakai konfigurasi backend aktif: `.env` untuk Supabase, atau tetapkan `AKADEMIKKITA_ENV_FILE` ke `.env.demo` untuk SQLite lokal. `data_source`, histori, dan respons API menandai data tambahan sebagai simulasi. Tabel perbandingan, detail sekolah, dan kartu rekomendasi menampilkan labelnya. `demo-init` tidak lagi mengimpor identitas sekolah fiktif.

Sebelum perluasan katalog, 18 identitas dummy di Supabase beserta 15 hasil rekomendasi terkait dibersihkan pada 21 Oktober 2026. Metadata simulasi awal dilengkapi untuk 18 sekolah asli di Supabase dan 130 sekolah asli pada SQLite lokal. Cadangan sebelum perubahan tersedia di `.audit-backup/` yang diabaikan Git.

Engine rekomendasi pada versi ini masih menggunakan model baseline. Data simulasi ditujukan untuk pengujian alur aplikasi, bukan penilaian penerimaan sekolah.

Tes fitur memakai SQLite sementara:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests/simulation -v
```

Tes mencakup pengisian ulang tanpa duplikat, pelestarian identitas/nilai yang sudah diisi, preview tanpa penyimpanan, login/profil, pencarian, detail, perbandingan, histori, generate, dan latest. Suite pytest lama masih terhalang impor `reflected_tables` pada `tests/conftest.py`; tes fitur ini dijalankan terpisah.

## Demo lengkap

```powershell
.\run-demo.ps1
```

Demo berjalan pada port **8001**, memakai `.env.demo` dan SQLite lokal terpisah. Script menyiapkan skema, sepuluh mapel, satu akun siswa, nilai, dan tes minat. Katalog sekolah yang sudah tersimpan tetap dipakai. Login lewat `/api/auth/login` memakai email `siswa@example.invalid` dan password `demo-akademikkita-123`.

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
