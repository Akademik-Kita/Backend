# Aturan rekomendasi v1.0

Model: `rule-based-v1.0`. Semua skor faktor dan skor akhir berada pada skala 0–100. Peluang memakai persen 0–100. Model ini tidak dilatih dengan machine learning.

## Nilai siswa

Rata-ratakan semua semester yang tersedia **per mata pelajaran**, kemudian rata-ratakan nilai antar mata pelajaran. Dengan demikian mapel yang memiliki enam semester tidak otomatis mendapat bobot lebih besar daripada mapel yang hanya memiliki dua. Baris berstatus `ditolak` tidak dipakai. Nilai belum terverifikasi tetap dapat dipakai pada MVP; verifikasi merupakan tugas modul profil.

Tidak ada bonus prestasi karena rumus pada paket tim tidak menetapkannya. `required_subjects` disimpan untuk penggunaan berikutnya, tetapi tidak mengubah rata-rata akademik pada versi ini. Bila tim menambahkan bobot mapel, ubah versi algoritma dan samakan definisi skor dengan sumber histori penerimaan.

## Kandidat dan histori

1. Ambil sekolah berjenis `SMA`, programnya, biaya, dan jalur melalui eager loading.
2. Terapkan preferensi kepemilikan. Jika daftar kosong, negeri/swasta sama-sama dipertimbangkan.
3. Hitung jarak garis lurus Haversine dari koordinat siswa ke sekolah.
4. Pilih biaya terbaru yang tidak berada di tahun kalender masa depan. Data tahun awal lebih tua dari tahun sebelumnya tidak dipakai.
5. Jika hard filter aktif, keluarkan kandidat dengan jarak > batas atau biaya bulanan > anggaran. Batas bersifat inklusif.
6. Periksa kuota >0, jenis skor, kelas yang didukung, nilai minimum tambahan, batas jarak jalur. Aturan yang belum didukung tidak dianggap otomatis terpenuhi.
7. Ambil histori tiga tahun kalender yang sudah selesai, misalnya 2023–2025 pada 2026; tahun dengan `accepted=0` tidak dipakai untuk scoring.
8. Untuk **setiap jalur secara terpisah**, bobot tahun paling lama hingga terbaru adalah 1, 2, 3 sesuai jumlah tahun tersedia. Minimum, rata-rata, dan maksimum dirata-ratakan dengan bobot itu. Jangan menggabungkan jalur yang memakai kriteria berbeda.
9. Pilih jalur eligible dengan skor peluang tertinggi; tie-break memakai UUID. Nama jalur yang dipilih disebutkan di penjelasan dan snapshot. Ini perkiraan jalur terbaik yang didukung, bukan prediksi peluang gabungan semua jalur.

Jika biaya, histori relevan, vektor minat, atau jalur yang didukung tidak tersedia, program dilewati. Jika semua kandidat habis, HTTP 409 menjelaskan bahwa kandidat belum tersedia. Jumlah program dilewati disimpan per alasan pada snapshot dan totalnya dicantumkan pada `message`.

## Lima faktor

`clip(x, a, b)` membatasi nilai x pada rentang a–b.

### Akademik

`A = clip(100 - 5 × abs(nilai_siswa - rata2_histori), 0, 100)`.

Nilai sama dengan rata-rata histori memberi 100; selisih 5 memberi 75; selisih 20 atau lebih memberi 0. Rumus simetris mengikuti aturan “makin dekat, makin tinggi”. Siswa yang jauh di atas rata-rata histori dapat memiliki skor kecocokan akademik lebih rendah sekaligus skor peluang lebih tinggi; kedua faktor mengukur hal berbeda.

### Minat

Cosine similarity enam dimensi RIASEC dikalikan 100. Urutan key tetap: `realistic`, `investigative`, `artistic`, `social`, `enterprising`, `conventional`. Nilai 0–100 dan nonnegatif. Vektor identik memberikan 100; ortogonal memberi 0. Fungsi matematika mengembalikan 0 untuk vektor nol agar tidak membagi nol, tetapi generate menolak tes siswa yang seluruh skornya nol.

### Peluang

Interpolasi linear dengan jangkar `nilai_minimum -> 35%`, `nilai_rata2 -> 65%`, `nilai_maksimum -> 85%`. Di bawah minimum atau di atas maksimum gunakan kemiringan 5 poin persen per satu poin nilai, lalu batasi skor tengah pada 5–95.

Jika beberapa jangkar memiliki nilai yang sama, gabungkan persentase jangkar tersebut dengan rata-rata. Jika ketiganya identik, gunakan `clip(65 + 5 × (nilai_siswa - rata2_histori), 5, 95)`. Hasil tetap monoton dan tidak membagi nol.

`peluang` dalam `score_breakdown` adalah skor tengah sebelum pembentukan rentang. Margin rentang = `10 + 5 × (3 - jumlah_tahun)`, lalu tambah 5 jika profil <80% atau kurang dari 10 mapel. `chance_low/high = clip(skor_tengah ± margin, 0, 100)`.

Rentang ini **bukan interval kepercayaan statistik**, dan tidak membuktikan probabilitas diterima. Data jumlah pendaftar, diterima, kuota, dan distribusi disimpan di database, tetapi belum digunakan untuk kalibrasi/ranking kuota pada versi ini. Semua rentang dan label heuristik harus diuji terhadap outcome nyata sebelum dijadikan prediksi statistik.

Kategori menggunakan skor tengah, bukan `total_score` atau salah satu batas rentang: <35 = `ambisius`; 35–70 inklusif = `realistis`; >70 = `aman`.

### Jarak

`J = clip(100 × (1 - jarak_km / max_distance_km), 0, 100)`.

Jarak 0 memberi 100; tepat batas maksimum memberi 0. Rumus sengaja menilai sekolah lebih dekat lebih tinggi. Kalimat paket “makin dekat distance_km ke max_distance_km” ditafsirkan mengikuti tujuan PRD, bukan memberi hadiah untuk sekolah di ujung batas preferensi.

Haversine menggunakan radius bumi 6.371,0088 km. Jarak tidak mewakili jalan, durasi perjalanan, ataupun zona penerimaan administratif.

### Biaya

Biaya berulang bulanan = `(tuition_per_period + other_fee) / periode`, dengan periode =1 untuk bulan dan =6 untuk semester.

Jika biaya <= anggaran, skor 100. Jika biaya > anggaran, `B = clip(100 × anggaran / biaya, 0, 100)`. Biaya nol dan anggaran nol memberi 100; biaya positif dengan anggaran nol memberi 0. Tidak ada pembagian nol.

Uang pangkal disimpan/dijelaskan terpisah karena kontrak siswa hanya memiliki anggaran per bulan, tanpa anggaran pembayaran awal. Model belum memperhitungkan transportasi, beasiswa yang belum disetujui, total sampai lulus, maupun keterjangkauan uang pangkal.

Dengan hard filter aktif, biaya di atas anggaran dikeluarkan sebelum scoring sehingga skor biaya kandidat tersisa 100. Dalam mode soft scoring, penalti biaya membedakan kandidat yang lebih mahal. Ini konsekuensi langsung FR-044, bukan bobot yang diabaikan oleh kode.

## Total, urutan, dan penjelasan

Bobot default: akademik .30, minat .25, peluang .20, jarak .15, biaya .10. Tiap bobot harus 0–1 dan total 1 dengan toleransi 1e-6. Bobot tidak dinormalisasi diam-diam; input salah menghasilkan 422.

Skor faktor dibulatkan dua desimal, lalu dihitung `total_score = Σ(skor_faktor × bobot_faktor)` dan dibulatkan dua desimal. Urut: total menurun, peluang menurun, jarak meningkat, UUID program meningkat. Rank mulai 1, satu hasil per program.

Penjelasan mengambil dua **skor faktor** tertinggi sebagai `positive` dan dua terendah sebagai `negative`, sesuai kontrak. Ini bukan dua kontribusi bobot terbesar. Faktor “negative” disebut faktor relatif terendah; skor 90 tetap bisa masuk kelompok ini tanpa disebut buruk. Keterbatasan heuristik/profil/data sintetis dicantumkan pada penjelasan dan `message` tanpa menambah field API baru.

## Penyimpanan dan reproducibility

`recommendation_runs.input_snapshot` menyimpan input siswa, bobot, mode filter, tahun perhitungan, nama sekolah/program, biaya, histori, jalur, sumber, koordinat kandidat dan versi algoritma. `recommendation_items` menyimpan seluruh skor, kategori dan alasan. Penyimpanan run/items dilakukan dalam satu transaksi.

`latest` mengambil hasil yang telah disimpan. Tidak memakai nama katalog terkini atau menghitung ulang berdasarkan profil terkini; perubahan setelah generate tidak mengubah hasil lama. Penghapusan profil menghapus run/item melalui foreign key cascade. Snapshot berisi data sensitif dan harus mengikuti perlindungan penyimpanan serta retensi proyek.

## Konfigurasi default

Backend terpadu memakai `RECOMMENDATION_HARD_FILTERS=false`. Kandidat di atas anggaran/jarak tetap mendapat skor rendah. Mode hard filter dapat diaktifkan secara eksplisit; metode scoring dan envelope API tetap sama.
