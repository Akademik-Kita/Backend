# Katalog sekolah dan kelengkapan sumber

Pemeriksaan sumber: 14 Oktober 2026. Wilayah awal: Kota Jakarta Selatan.

## Katalog resmi

`data/schools-jakarta-selatan.json` berisi 18 SMA dari Kebayoran Baru, Tebet, dan Kebayoran Lama. Setiap record memiliki sumber resmi terpisah:

- [Daftar SMA Kebayoran Baru](https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen/016306/3/all/13/all)
- [Daftar SMA Tebet](https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen/016309/3/all/13/all)
- [Daftar SMA Kebayoran Lama](https://referensi.data.kemendikdasmen.go.id/pendidikan/dikmen/016305/3/all/13/all)
- [Contoh identitas dan koordinat SMAN 8 Jakarta](https://referensi.data.kemendikdasmen.go.id/pendidikan/npsn/20102568)

Yang diperiksa: nama, NPSN, status, alamat, kecamatan, akreditasi, kontak/website yang tersedia, dan koordinat. Program, fasilitas, biaya serta histori seleksi belum diverifikasi. Daftar kosong berarti belum tersedia, bukan biaya gratis atau sekolah tanpa program.

Pengumpul sumber dapat dijalankan kembali:

```powershell
.\.venv\Scripts\python.exe scripts\collect_schools.py --checked-at "2026-10-14T00:00:00+07:00"
```

Tanggal harus diganti dengan waktu pemeriksaan yang sebenarnya. Collector membatasi host sumber resmi dan memeriksa koordinat berada di wilayah Jakarta Selatan.

## Batas sumber

Sumber Kemendikdasmen menyediakan identitas satuan pendidikan. Sumber tersebut tidak memuat biaya atau ringkasan nilai minimum/rata-rata/maksimum seleksi 2023-2025 pada skala rapor 0-100. Informasi biaya dan jalur dari sekolah/PPDB perlu mempunyai lingkup serta definisi skala yang jelas sebelum diimpor. Status negeri tidak otomatis diterjemahkan menjadi biaya nol.

## Data yang diperlukan agar sekolah masuk rekomendasi

Untuk tiap sekolah/program, lengkapi JSON dengan:

1. Nama program dan vektor RIASEC enam dimensi sebagai konfigurasi aturan yang sudah direview.
2. Biaya berulang dengan periode bulan/semester dan tahun ajaran; `other_fee` hanya biaya yang berulang pada periode sama. Biaya sekali di awal masuk `entrance_fee`.
3. Jalur seleksi, kuota, aturan kelayakan, dan histori tiga tahun selesai terakhir pada skala rata-rata rapor 0–100. Cantumkan URL/dokumen asal dalam `history.source`.

Importer memvalidasi rentang dan relasi sebelum menulis. ID tetap dipertahankan ketika record diperkaya. Program yang belum mempunyai biaya/histori relevan dilewati; bila seluruh katalog belum lengkap, generate menghasilkan 409 dengan pesan yang menjelaskan kekurangan data.

## Demonstrasi algoritma

`data/schools-demo.json` seluruhnya sintetis: 18 sekolah, 54 program, 108 jalur dan 324 histori. File ini hanya dipakai SQLite lokal melalui `run-demo.ps1`. Backend dan endpoint demo menggunakan model akun asli serta login biasa, sehingga seluruh alur frontend dapat diuji tanpa memasukkan angka sintetis ke sekolah nyata.
