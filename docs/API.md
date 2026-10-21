# Kontrak API

Seluruh sukses: `{"success":true,"data":...,"message":"..."}`.
Seluruh error: `{"success":false,"data":null,"message":"..."}`.

| Endpoint | Akses |
|---|---|
| POST `/auth/register`, POST `/auth/login` | Publik |
| GET `/auth/me` | Token |
| GET/PUT `/profile` | Siswa pemilik profil |
| GET `/profile/subjects` | Publik |
| POST/GET `/profile/academic-records` | Siswa |
| PUT/DELETE `/profile/academic-records/{id}` | Pemilik nilai |
| POST/GET `/profile/achievements` | Siswa |
| DELETE `/profile/achievements/{id}` | Pemilik prestasi |
| POST `/profile/interest-assessment` | Siswa |
| GET `/profile/interest-assessment/latest` | Siswa |
| GET `/schools` | Publik; token opsional untuk jarak |
| GET `/schools/compare?ids=...` | Publik; 1–4 UUID unik |
| GET `/schools/{id}` | Publik |
| GET `/schools/{id}/jurusan/{jurusan_id}/riwayat-penerimaan` | Publik |
| POST `/recommendations/generate` | Token pemilik profil |
| GET `/recommendations/latest` | Token pemilik hasil |

Header autentikasi: `Authorization: Bearer <access_token>`. Token berasal dari `/auth/login`. Role `orang_tua` dapat register/login tetapi belum memiliki mekanisme hubungan akun–anak dalam kontrak ini.

GET `/schools` menerima `search` (nama/NPSN atau nama wilayah kecamatan, kota/kabupaten, dan provinsi), `kecamatan`, `ownership`, `accreditation`, dan `page`; ukuran halaman 10, `data` tetap array. Pencarian wilayah menyertakan sekolah pada wilayah turunannya. Spasi tepi diabaikan dan karakter `%`/`_` diperlakukan sebagai teks. Compare mengikuti urutan ID masukan. `data_is_simulated` menandai metadata tambahan buatan untuk pengujian. Histori menyertakan `quota`, `applicants`, `accepted`, dan `source`. Endpoint runtime memakai prefix `/api`.

PUT profil hanya mengubah field yang dikirim. `id`, `user_id` dan `profile_completeness` tidak dapat diubah oleh klien. Koordinat dapat diubah satu per satu; lokasi belum lengkap tidak dapat dipakai untuk generate.

POST generate dapat tanpa body atau `{}`. Bobot default masing-masing .20 untuk akademik, minat, peluang, jarak, dan biaya. Bobot custom dikirim pada `weights`. Hasil dibatasi 50 sekolah dengan skor tertinggi; seluruh katalog tetap dapat dicari lewat `/schools`.

Enam key tes minat: `realistic`, `investigative`, `artistic`, `social`, `enterprising`, `conventional`, masing-masing 0–100. Nama sekolah/jurusan pada rekomendasi tetap `school_id`, `school_name`, `jurusan_id`, `jurusan_name`.

Response rekomendasi memuat `weights` dan `recommendations` berisi rank, total_score, score_breakdown, chance_low/high, category, data_is_simulated, dan explanation positive/negative. Bentuk lengkap field tersedia pada `openapi.json`. Perhitungan masih memakai model baseline; data simulasi dan peluang bukan data penerimaan resmi.

HTTP 401 untuk token tidak valid; 403 untuk fitur profil yang diakses role selain siswa; 404 untuk data yang tidak ditemukan; 409 untuk profil/katalog yang belum cukup; 422 untuk input di luar kontrak; 503 untuk database belum siap.
