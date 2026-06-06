# CEPAT — Sistem Multi-Agent Respons Bencana Gempa

**CEPAT** (Cepat Emergency Planning and Action Tool) adalah sistem berbasis Large Language Model (LLM) yang dirancang untuk membantu petugas BPBD (Badan Penanggulangan Bencana Daerah) dalam mengoordinasikan respons bencana gempa bumi secara lebih cepat dan terstruktur.

---

## Kesesuaian dengan Deskripsi Sistem

| Fitur | Deskripsi | Status |
|---|---|---|
| Multi-agent LLM | 5 agen AI bekerja secara paralel | ✅ Diimplementasikan |
| Monitoring Agent | Pantau BMKG real-time, deteksi M ≥ 5 | ✅ Diimplementasikan |
| Intelligence Agent | Kumpul berita RSS + filter hoaks via LLM | ✅ Diimplementasikan (RSS feeds; social media belum) |
| Analysis Agent | Situation Report + penilaian risiko (LOW/MEDIUM/HIGH/CRITICAL) | ✅ Diimplementasikan |
| Communication Agent | Draf alert Bahasa Indonesia, Bahasa Minang, & laporan teknis | ✅ Diimplementasikan |
| Coordination Agent | Peta sumber daya + rencana aksi berprioritas (P1/P2/P3) | ✅ Diimplementasikan |
| Dashboard web terpusat | Flask + SQLite | ✅ Diimplementasikan |
| Human-in-the-loop | Approval queue sebelum eksekusi | ✅ Diimplementasikan |
| Gemini API | LLM untuk analisis & generasi teks | ✅ Diimplementasikan |
| Python + Flask + SQLite | Stack teknis | ✅ Diimplementasikan |
| CrewAI / LangGraph | Framework orkestrasi agent | ⚠️ Diganti custom `Orchestrator` berbasis Python threading |

> **Catatan penting:** Orkestrasi pipeline dibangun sendiri menggunakan `threading.Thread` dan class `Orchestrator` tanpa framework CrewAI atau LangGraph. Fungsionalitas setara — pipeline berjalan Monitoring → Intelligence → Analysis → Communication → Coordination — namun lebih ringan dan tanpa dependensi tambahan.

---

## Arsitektur Sistem

```
BMKG API ──────► Monitoring Agent ──────► SQLite Database
                                                │
RSS Feeds ─────► Intelligence Agent ────────────┤
                      │ Gemini API              │
                      ▼                         │
                Analysis Agent ─────────────────┤
                      │ Gemini API              │
                      ▼                         │
              Communication Agent ──────────────┤
                      │ Gemini API              │
                      ▼                         │
              Coordination Agent ───────────────┘
                        │ Gemini API
                        ▼
              Flask Web Dashboard ◄──── Petugas BPBD
               (Approval Queue)         Human-in-the-loop
```

---

## Prasyarat

- **Python 3.10 atau lebih baru** (diuji pada 3.11 dan 3.13)
- **pip** (package manager Python)
- Koneksi internet aktif (untuk BMKG API, RSS feeds, dan Gemini API)
- Browser modern: Chrome, Firefox, atau Edge

---

## Instalasi

### 1. Masuk ke folder project

```bash
cd CEPAT
```

### 2. Install semua dependencies

```bash
pip install -r requirements.txt
```

Package yang akan diinstall:

| Package | Versi Min | Fungsi |
|---|---|---|
| `flask` | 3.0.0 | Web server & REST API |
| `requests` | 2.31.0 | HTTP request ke BMKG & RSS |
| `python-dotenv` | 1.0.0 | Baca konfigurasi dari file `.env` |
| `google-genai` | 1.0.0 | Gemini API client (LLM) |
| `feedparser` | 6.0.11 | Parse RSS feed berita |

### 3. Buat file konfigurasi `.env`

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Buka file `.env` dan sesuaikan nilainya (lihat bagian **Konfigurasi** di bawah).

---

## Konfigurasi

Buka file `.env` dan isi sesuai kebutuhan:

```env
# ── Monitoring Agent ─────────────────────────────────────────
POLL_INTERVAL=300          # Interval polling BMKG (detik). Default: 300 = 5 menit
MAGNITUDE_THRESHOLD=5.0    # Batas magnitudo untuk trigger alert
BMKG_TIMEOUT=10            # Timeout HTTP request ke BMKG (detik)

# ── Gemini API ───────────────────────────────────────────────
# Kosongkan untuk mode demo/fallback tanpa LLM
GEMINI_API_KEY=AIza...
GEMINI_HOAX_MODEL=gemini-2.0-flash
GEMINI_ANALYSIS_MODEL=gemini-2.0-flash
GEMINI_COMM_MODEL=gemini-2.0-flash
GEMINI_COORD_MODEL=gemini-2.0-flash
GEMINI_MAX_TOKENS=1500

# ── Intelligence Agent ────────────────────────────────────────
RSS_TIMEOUT=8              # Timeout fetch RSS feed (detik)
RSS_MAX_AGE_HOURS=24       # Hanya ambil berita dalam 24 jam terakhir

# ── Pipeline ──────────────────────────────────────────────────
PIPELINE_MIN_MAGNITUDE=5.0    # Magnitudo minimum untuk jalankan pipeline AI
PIPELINE_MAX_INTEL=10         # Maks artikel berita per gempa yang diproses

# ── Database ─────────────────────────────────────────────────
DATABASE_PATH=database/cepat.db

# ── Flask Dashboard ───────────────────────────────────────────
FLASK_SECRET_KEY=ganti-dengan-kunci-rahasia-yang-kuat
FLASK_DEBUG=False
FLASK_PORT=5000
FLASK_HOST=0.0.0.0
```

### Mendapatkan Gemini API Key

1. Buka [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
2. Login dengan akun Google
3. Klik **"Create API Key"**
4. Salin key (format: `AIzaSy...`) dan tempel ke `.env` pada `GEMINI_API_KEY=`

> Gemini API memiliki **tier gratis** yang cukup untuk pengembangan dan demo.

---

## Menjalankan Project

### Mode A — Dashboard Web Lengkap (Rekomendasi)

```bash
python dashboard/app.py
```

Setelah berjalan, buka browser ke:
- **Dashboard utama:** http://localhost:5000 (Semua tab monitoring, situasi, analisa, serta antrean persetujuan/Queue sudah terintegrasi di sini)

Output terminal normal:
```
2024-xx-xx  [INFO]  database.db_handler: Database diinisialisasi: database/cepat.db
2024-xx-xx  [WARNING]  IntelligenceAgent: GEMINI_API_KEY tidak diset — fallback mode
...
 * Running on http://0.0.0.0:5000
```

---

### Mode B — Demo Otomatis (Untuk Presentasi)

Jalankan skenario gempa historis **M6.2 Pasaman Barat 2022** secara otomatis:

```bash
# Tanpa API key (mode fallback — rule-based)
python tests/demo_scenario.py --no-api

# Dengan Gemini API key aktif (mode LLM)
python tests/demo_scenario.py --api
```

Demo ini akan:
1. Insert data gempa M6.2 ke database
2. Insert 6 laporan berita (5 valid + 1 hoaks)
3. Jalankan Analysis → Communication → Coordination Agent
4. Tampilkan ringkasan semua output di terminal

---

### Mode C — Test Koneksi BMKG Saja

```bash
python agents/monitoring_agent.py
```

Ini menjalankan satu siklus polling ke BMKG dan menampilkan hasilnya di terminal.

---

## Alur Penggunaan Dashboard

### Langkah 1 — Ambil Data Gempa
Klik tombol **"Fetch BMKG"** di dashboard. Sistem mengambil data gempa terkini dari API BMKG dan menyimpannya ke database.

### Langkah 2 — Jalankan Pipeline Analisis
Pada tabel daftar gempa, gempa dengan M ≥ 5.0 menampilkan tombol **"Analisis"**. Klik untuk menjalankan pipeline lengkap:

| Urutan | Agent | Output |
|---|---|---|
| 1 | Intelligence Agent | Kumpul berita terkait + klasifikasi VALID/HOAX/UNVERIFIED |
| 2 | Analysis Agent | Situation Report + level risiko |
| 3 | Communication Agent | 3 draf pesan (Bahasa Indonesia, Minang, Teknis) |
| 4 | Coordination Agent | Peta kebutuhan sumber daya + 5 aksi prioritas |

### Langkah 3 — Review & Approval
Buka tab **Queue** di dashboard utama. Petugas BPBD dapat:
- ✅ **Setujui** draf untuk dikirim/dieksekusi
- ✏️ **Edit** konten sebelum disetujui
- ❌ **Tolak** draf yang tidak sesuai
- 📋 Lihat **Audit Log** semua keputusan dan petugas yang bertanggung jawab

---

## Struktur Project

```
CEPAT/
├── agents/
│   ├── monitoring_agent.py      # Polling BMKG setiap N menit, simpan ke DB
│   ├── intelligence_agent.py    # Fetch RSS + filter hoaks via Gemini
│   ├── analysis_agent.py        # Generate Situation Report via Gemini
│   ├── communication_agent.py   # Draft 3 versi pesan alert via Gemini
│   ├── coordination_agent.py    # Peta sumber daya + rencana aksi via Gemini
│   └── orchestrator.py          # Koordinator pipeline (background thread)
├── dashboard/
│   ├── app.py                   # Flask server + semua REST API endpoints
│   ├── static/
│   │   └── logo.png
│   └── templates/
│       ├── index.html           # Dashboard utama (peta, stats, tabel)
│       └── approval_queue.html  # Halaman persetujuan draf
├── database/
│   ├── schema.sql               # Definisi skema semua tabel SQLite
│   ├── db_handler.py            # Layer akses database (CRUD operations)
│   └── cepat.db                 # File database SQLite (dibuat otomatis)
├── prompts/
│   ├── hoax_filter.txt          # Prompt: klasifikasi kredibilitas berita
│   ├── situation_report.txt     # Prompt: generate Situation Report
│   ├── communication_alert.txt  # Prompt: draft pesan alert
│   └── coordination_plan.txt    # Prompt: rencana koordinasi lapangan
├── tests/
│   └── demo_scenario.py         # Skenario demo gempa Pasaman Barat 2022
├── config.py                    # Semua konfigurasi sistem (baca dari .env)
├── requirements.txt             # Daftar dependencies Python
├── .env.example                 # Template konfigurasi (salin ke .env)
└── README.md                    # Dokumentasi ini
```

---

## REST API Endpoints

| Method | Endpoint | Deskripsi |
|---|---|---|
| `GET` | `/` | Halaman dashboard utama (dengan tab Queue terintegrasi) |
| `GET` | `/api/earthquakes` | Semua data gempa (max 200) |
| `POST` | `/api/earthquakes/:id/acknowledge` | Tandai gempa sebagai diakui |
| `GET` | `/api/stats` | Statistik + status orchestrator |
| `POST` | `/api/agent/poll` | Paksa polling BMKG + pipeline sekarang |
| `GET` | `/api/situation-reports` | Semua Situation Reports |
| `GET` | `/api/situation-reports/:eq_id` | Sitrep satu gempa |
| `POST` | `/api/pipeline/:eq_id` | Trigger pipeline manual untuk satu gempa |
| `GET` | `/api/intelligence` | Semua laporan berita |
| `GET` | `/api/intelligence/:eq_id` | Berita untuk satu gempa |
| `GET` | `/api/approval/drafts` | Semua draf pesan |
| `GET` | `/api/approval/drafts/pending` | Draf yang menunggu persetujuan |
| `POST` | `/api/approval/draft/:id/approve` | Setujui draf |
| `POST` | `/api/approval/draft/:id/reject` | Tolak draf |
| `POST` | `/api/approval/draft/:id/edit` | Edit konten draf |
| `GET` | `/api/approval/plans` | Semua rencana koordinasi |
| `POST` | `/api/approval/plan/:id/approve` | Setujui rencana koordinasi |
| `POST` | `/api/approval/plan/:id/reject` | Tolak rencana koordinasi |
| `GET` | `/api/audit-log` | Log semua keputusan petugas |

---

## Perbedaan Mode Fallback vs LLM

| Fitur | Tanpa `GEMINI_API_KEY` | Dengan `GEMINI_API_KEY` |
|---|---|---|
| Peta gempa real-time | ✅ | ✅ |
| Data BMKG | ✅ | ✅ |
| Kumpul berita RSS | ✅ | ✅ |
| Klasifikasi hoaks | Semua `UNVERIFIED` | AI: `VALID` / `HOAX` / `UNVERIFIED` |
| Situation Report | Template otomatis berbasis aturan | AI-generated, kontekstual |
| Draf pesan alert | Template sederhana | AI-generated, natural language |
| Rencana koordinasi | Template berdasar level risiko | AI-generated, spesifik lokasi |

---

## Pipeline Status Gempa

| Status | Keterangan |
|---|---|
| `PENDING` | Gempa M ≥ 5, menunggu diproses pipeline |
| `PROCESSING` | Sedang diproses agent |
| `DONE` | Pipeline selesai, sitrep tersedia |
| `FAILED` | Pipeline gagal (lihat log terminal) |
| `SKIPPED` | Magnitudo di bawah threshold, tidak diproses |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'flask'`**
```bash
pip install -r requirements.txt
```

**Port 5000 sudah dipakai**
```env
# Di file .env, ubah:
FLASK_PORT=5001
```
Lalu akses http://localhost:5001

**Peta tidak muncul**
Pastikan perangkat terhubung internet. Tile peta diambil dari OpenStreetMap.

**Data gempa tidak muncul setelah Fetch BMKG**
BMKG API kadang lambat atau down. Coba beberapa saat lagi.

**Pipeline error dengan API key aktif**
- Pastikan format key benar (diawali `AIza`)
- Cek quota di [Google AI Studio](https://aistudio.google.com/)
- Coba ganti model ke `gemini-1.5-flash` di `.env` jika model default tidak tersedia

---

## Stack Teknologi

| Komponen | Teknologi |
|---|---|
| Backend | Python 3.10+, Flask 3.x |
| Database | SQLite (file lokal, tanpa server) |
| LLM | Google Gemini 2.0 Flash via `google-genai` |
| Data Gempa | BMKG REST API (publik, tanpa API key) |
| Data Berita | RSS Feed: ANTARA, Detik, Tribun, Google News |
| Frontend | HTML/CSS/JS vanilla, Bootstrap 5, Leaflet.js |
| Peta | OpenStreetMap (via Leaflet) |
| Orkestrasi Agent | Custom `Orchestrator` class (Python `threading`) |
