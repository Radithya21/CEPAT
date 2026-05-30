# Poster Reference

## 1. Poster PlanMax
- Nama Proyek: PLANMAX
- Acara: MSU iReX EXPO 2025
- Kreator: Muhammad Nouval Habibie
- Value Proposition: Perencanaan proyek cerdas dan kolaborasi tim berbasis AI (AI-based Project Management for Smarter Collaboration).
- Masalah yang Diselesaikan (Key Challenges): Kurangnya kolaborasi tim, kesulitan dalam melacak progres, tidak adanya deteksi hambatan sejak dini, dan tenggat waktu yang sering terlewat yang menurunkan produktivitas.

### Fitur Utama (Key Features)
- Interactive Gantt Chart: Visualisasi timeline dan progres proyek secara real-time.
- Obstacle & Duration Prediction: Mendeteksi hambatan secara otomatis dan memprediksi durasi sebuah tugas.
- Productivity Gamification: Sistem poin, level, dan papan peringkat (leaderboard) untuk memotivasi tim.
- Risk Management & Mitigation: Identifikasi dan penanganan risiko dalam proyek.
- Team Workload Mapping: Visualisasi distribusi beban kerja untuk mengoptimalkan alokasi sumber daya tim.
- AI Timeline Generator: Pembuatan struktur dan perencanaan proyek otomatis hanya melalui satu prompt.
- Kesesuaian SDGs (Sustainable Development Goals): Mendukung SDG 8 (Pekerjaan Layak dan Pertumbuhan Ekonomi) dan SDG 9 (Industri, Inovasi, dan Infrastruktur).

## 2. Poster Tangkapin
- Nama Proyek: Tangkapin (A Weapon Crime Detection System and Automatic Reporting).
- Asal Institusi: Sistem Informasi, Fakultas Teknologi Informasi, Universitas Andalas.
- Kreator: Muhammad Fariz, Naufal, Mhd Ulil Abshar.
- Latar Belakang Masalah (Background): Kejahatan properti dengan kekerasan masih tinggi di provinsi padat penduduk di Indonesia. Penurunan data kasus sebenarnya mencerminkan kurangnya pelaporan, bukan penurunan kejahatan itu sendiri. Pelaku perampokan minimarket sering menggunakan pisau/senjata tajam dan kerap lolos karena pelaporan yang terlambat.
- Tujuan (Objectives): Meningkatkan keamanan publik melalui deteksi dini, mempercepat pelaporan polisi, meningkatkan angka penangkapan, mengurangi tingkat kejahatan ritel, dan memajukan SDG 16.

### Solusi yang Ditawarkan (Proposed Solution)
- Sistem AI deep learning PyTorch dengan akurasi 94% untuk mendeteksi senjata (pisau dan pistol) yang dilatih menggunakan 2.000 gambar.
- Menghasilkan laporan digital komprehensif dalam 2 detik setelah deteksi, lengkap dengan bukti visual, detail toko, dan koordinat lokasi.
- Algoritma untuk mengidentifikasi dan memberi tahu kantor polisi terdekat.
- Dasbor terpadu dengan integrasi GPS untuk memantau status insiden, lokasi petugas, dan waktu respons.

### Alur Sistem (Flow System)
Input dari CCTV $\rightarrow$ Deteksi senjata $\rightarrow$ Diproses model ML $\rightarrow$ Klasifikasi senjata $\rightarrow$ Simpan bukti & buat dokumen laporan otomatis $\rightarrow$ Kirim ke pemilik dan polisi terdekat secara realtime $\rightarrow$ Penugasan polisi ke lokasi.

- Dampak Proyek (Project Impact): Mengurangi kejahatan, memangkas waktu respons polisi melalui pelaporan otomatis, meningkatkan penuntutan yang sukses melalui bukti digital, dan berkontribusi langsung pada SDG 16 (Peace, Justice and Strong Institutions).

## 3. Poster StunBy
- Nama Proyek: StunBy: Indonesian Baby Growth Tracking App.
- Asal Institusi: Departemen Sistem Informasi, Fakultas Teknologi Informasi, Universitas Andalas.
- Kreator: Naufal and Team.
- Latar Belakang Masalah (Background): Menurut data Kementerian Kesehatan tahun 2023, 21,5% balita di Indonesia menderita stunting, menempatkan Indonesia di peringkat ke-27 secara global dari 154 negara. Penyebab utamanya adalah kurangnya pengetahuan orang tua, gizi yang tidak memadai, serta pemantauan yang jarang karena hanya bergantung pada kunjungan Posyandu bulanan.
- Tujuan Proyek (Project Goal): Memberikan solusi yang efisien dan mudah digunakan untuk memantau serta mencegah stunting pada anak melalui deteksi pengukuran tubuh yang akurat dan wawasan pertumbuhan yang dipersonalisasi.

### Fitur Utama (Key Features)
- Stunting Detection: Sistem pengukuran berbasis Machine Learning (ML) yang memanfaatkan uang koin sebagai skala pembanding dalam foto.
- Nutritional Recommendations: Saran diet/nutrisi yang dipersonalisasi berdasarkan data pertumbuhan anak.
- Growth Monitoring: Pelacakan tinggi badan, berat badan, dan indikator pertumbuhan lainnya secara real-time menggunakan grafik yang mudah dibaca.
- Educational Resources: Konten edukasi yang disesuaikan bagi orang tua untuk memahami dan mendukung perkembangan anak.

- Manfaat dan Dampak (Benefits and Impact): Memberikan dampak positif pada kesehatan masyarakat melalui deteksi dini dan intervensi. Ada juga manfaat jangka panjang berupa peningkatan kesadaran dan akses ke data pertumbuhan, terutama di daerah tertinggal.
- Alur Sistem (Flow System): Ditampilkan secara visual melalui antarmuka aplikasi; menunjukkan kamera ponsel yang mendeteksi tubuh bayi beserta koin sebagai skala, dilanjutkan dengan halaman input data bayi, dan grafik pertumbuhan real-time.

## 4. Data Poster SIApo
- Nama Proyek: SIApo: A Pharmacy Management and Sales Forecasting System for Iliran Farma Using the Holt-Winters Method.
- Kreator: Thomas Nobel Asfar dari Departemen Sistem Informasi, Universitas Andalas.
- Latar Belakang Masalah: Banyak apotek masih mengandalkan sistem manual yang menyebabkan kesalahan, penundaan, dan pemborosan. Di Iliran Farma, sistem yang ada tidak memiliki dukungan multi-unit dan peramalan, sehingga berisiko memicu kelebihan stok dan inventaris kedaluwarsa.
- Metode dan Teknologi: Sistem ini menggunakan pendekatan hybrid microservice untuk memisahkan logika forecasting dari logika inti. Tumpukan teknologi yang digunakan mencakup Bun, Hono, FastAPI, PostgreSQL, dan React.

### Fitur Utama
- Product and Multi-Unit Management: Mendukung konversi unit untuk penentuan harga dan pelacakan stok yang akurat.
- Automated Stock Forecasting: Memprediksi permintaan menggunakan data historis.
- Transaction Management: Menangani pembelian dari pemasok dan penjualan ke pelanggan.
- Expiration & Low Stock Alerts: Mencegah kekosongan stok dan produk kedaluwarsa.
- Dynamic Reporting: Melacak kinerja keuangan dan inventaris.

- Dampak Proyek: Meningkatkan akurasi kontrol inventaris, mengurangi pemborosan obat, mempercepat layanan apotek, serta mendukung SDG 3 (Kehidupan Sehat dan Sejahtera) dan SDG 12 (Konsumsi dan Produksi yang Bertanggung Jawab).
- Kesimpulan: SIApo adalah solusi terukur (scalable) yang dapat diterapkan ke apotek lain yang menghadapi tantangan pengendalian stok serupa.

