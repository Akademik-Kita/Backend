# Verifikasi backend

Tanggal: 14 Oktober 2026. Lingkungan: Windows, Python 3.14.

- 64 tes otomatis lulus pada SQLite sementara.
- Ruff lulus setelah perubahan nama paket.
- Demo lokal: login akun asli, generate 54 rekomendasi, dan latest berhasil.
- Paket utama: crud_database dan machine_learning_recommendation_system.
- Satu aplikasi FastAPI, metadata SQLAlchemy bersama, dan satu perintah migrasi.
- Skema PostgreSQL berhasil diadopsi ke revision 20261014_01 tanpa membangun ulang tabel. RLS 15/15 aktif.
- Katalog 18 SMA Jakarta Selatan dikumpulkan dari sumber resmi; biaya/program/histori belum lengkap untuk rekomendasi nyata.

## Pemulihan PostgreSQL yang masih menunggu persetujuan

Percobaan tes PostgreSQL melalui pooler tidak menjaga schema sementara secara konsisten. Proses tes telah dihentikan. Dampak yang ditemukan: akun/katalog demo masuk schema public, nama sekolah resmi berubah, dan anggaran pada satu profil lama menjadi 0.

Skrip scripts/repair_audit_data.py disiapkan untuk menghapus hanya data audit yang diketahui, memulihkan nama resmi, dan mengembalikan anggaran ke nilai semula yang dikonfirmasi pengguna. Mode apply membutuhkan parameter --restore-budget; pelaksanaan belum dilakukan karena peninjauan persetujuan otomatis meminta izin khusus untuk penghapusan di database bersama.

Tes otomatis kini hanya memakai SQLite sementara, mengabaikan .env aplikasi, dan menolak TEST_DATABASE_URL eksternal sebelum koneksi. Hasil tes PostgreSQL yang gagal tidak dicatat sebagai verifikasi lulus.
