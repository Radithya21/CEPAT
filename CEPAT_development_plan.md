# CEPAT — Rencana Pengembangan Lanjutan

> Dokumen ini adalah panduan teknis bertahap untuk AI/developer yang melanjutkan project.
> Baca seluruh dokumen sebelum mulai mengerjakan agar memahami konteks dan ketergantungan antar-task.

---

## Konteks Project

CEPAT adalah sistem monitoring dan respons bencana gempa bumi untuk BPBD (Badan Penanggulangan Bencana Daerah).
Stack: **Python Flask** (backend) + **SQLite** (database) + **React via Babel CDN** (frontend, satu file HTML) + **Google Gemini API** (LLM agent).

**Struktur direktori penting:**
```
CEPAT/
├── agents/
│   ├── orchestrator.py          # Koordinator semua agent (background thread)
│   ├── monitoring_agent.py      # Poll BMKG setiap 5 menit
│   ├── intelligence_agent.py    # Scraping RSS berita + klasifikasi hoax
│   ├── analysis_agent.py        # Generate Situation Report (sitrep)
│   ├── communication_agent.py   # Generate 3 draf pesan (akan jadi 4)
│   └── coordination_agent.py    # Generate rencana koordinasi lapangan
├── dashboard/
│   ├── app.py                   # Flask routes dan REST API
│   └── templates/
│       ├── dashboard_v5.html    # Frontend utama (React + Leaflet)
│       └── approval_queue.html  # Halaman approval terpisah
├── database/
│   ├── db_handler.py            # Semua operasi SQLite
│   └── schema.sql               # Definisi tabel
├── prompts/
│   ├── hoax_filter.txt          # Prompt LLM untuk Intelligence Agent
│   ├── situation_report.txt     # Prompt LLM untuk Analysis Agent
│   ├── communication_alert.txt  # Prompt LLM untuk Communication Agent
│   └── coordination_plan.txt    # Prompt LLM untuk Coordination Agent
├── config.py                    # Semua konfigurasi (baca dari .env)
└── requirements.txt
```

**State saat ini (~55-60% selesai):**
- ✅ Backend Flask + semua REST API
- ✅ 5 agent berfungsi (dengan fallback tanpa LLM)
- ✅ DB SQLite lengkap
- ✅ Dashboard utama menampilkan data real dari DB
- ❌ Navigasi bottom nav tidak berfungsi (semua tab tampilkan halaman sama)
- ❌ Tidak ada halaman login
- ❌ Communication Agent hanya 3 draf (belum ada Inggris)
- ❌ Peta Leaflet belum interaktif (tidak ada daftar titik gempa)
- ❌ Coordination Agent tidak ada halaman tampilan di frontend
- ❌ Tidak ada integrasi Telegram
- ❌ Bug: KPI "Orchestrator Mode" selalu STANDBY

---

## TAHAP 1 — MUDAH
> Estimasi: dapat dikerjakan dalam satu sesi. Tidak ada perubahan arsitektur, hanya fix bug dan penambahan field kecil.

---

### T1.1 — Fix Bug KPI "Orchestrator Mode"

**File yang diubah:** `dashboard/app.py`

**Masalah:** Fungsi `api_stats()` menggabungkan data dari `orchestrator.get_status()` ke dalam key `"agent"`. Frontend membaca `stats.agent.mode` dan `stats.agent.cycles`, tapi backend tidak menyediakan kedua field itu. Yang ada adalah `is_running` dan `cycle_count`.

**Yang harus dilakukan:**
Di dalam fungsi `api_stats()` di `app.py`, sebelum data dikirim ke frontend, tambahkan transformasi:
```python
status = orchestrator.get_status()
agent_formatted = {
    **status,
    "mode": "ACTIVE" if status.get("is_running") else "STANDBY",
    "cycles": status.get("cycle_count", 0),
}
```
Ganti `"agent": status` menjadi `"agent": agent_formatted`.

**Hasil yang diharapkan:**
- KPI "Orchestrator Mode" tampil `ACTIVE` saat server berjalan
- KPI "Siklus" menampilkan angka yang terus bertambah setiap polling (setiap 5 menit)

---

### T1.2 — Tambah Draf Bahasa Inggris (Communication Agent: 3 → 4 Draf)

**File yang diubah:** `agents/communication_agent.py` dan `prompts/communication_alert.txt`

**Konteks:** Communication Agent saat ini menghasilkan 3 draf per gempa:
1. `public_id` — bahasa Indonesia maks 160 karakter
2. `public_minang` — bahasa Minang untuk komunitas Sumatera Barat
3. `technical` — laporan teknis formal

**Yang harus dilakukan:**

**A. Update `prompts/communication_alert.txt`:**
Tambahkan instruksi untuk output ke-4 dalam JSON:
```json
"english": "English public alert (max 200 chars): magnitude, location, safety advice"
```
Format output JSON yang diharapkan dari LLM harus jadi 4 key: `public_id`, `public_minang`, `technical`, `english`.

**B. Update `agents/communication_agent.py`:**
- Di method `_generate_llm_drafts()`: tambahkan parsing key `"english"` dari respons JSON
- Di method `_generate_fallback_drafts()`: tambahkan pembuatan draf bahasa Inggris secara template:
  ```python
  english = f"EARTHQUAKE M{mag} {loc}. Risk Level: {risk}. Follow BPBD instructions. Avoid damaged buildings."
  english = english[:200]
  ```
- Di method `run()`: tambahkan tuple `("english", drafts_data.get("english", ""))` ke dalam `draft_types`

**Catatan penting:** Field `draft_type` di tabel `communication_drafts` di DB sudah `TEXT` bebas, jadi tidak perlu migrasi DB.

**Hasil yang diharapkan:**
- Setiap gempa M≥5 yang diproses akan menghasilkan 4 draf bukan 3
- Draf `english` muncul di halaman approval dan di halaman laporan

---

### T1.3 — Fix Tombol "Edit" Draf di Dashboard

**File yang diubah:** `dashboard/templates/dashboard_v5.html`

**Masalah:** Tombol "✎ Edit" pada komponen `ACard` tidak memiliki `onClick` handler.

**Yang harus dilakukan:**
Tambahkan modal edit sederhana (popup) menggunakan React state. Ketika tombol Edit diklik:
1. Muncul textarea dengan isi konten draf saat ini
2. Ada tombol "Simpan" yang memanggil `POST /api/approval/draft/{id}/edit` dengan body `{content: "..."}`
3. Ada tombol "Batal" untuk menutup modal

**Endpoint backend yang tersedia:** `POST /api/approval/draft/<int:draft_id>/edit` sudah ada di `app.py`. Tidak perlu membuat endpoint baru.

---

### T1.4 — Ganti Seismogram dengan Grafik Frekuensi Gempa Real

**File yang diubah:** `dashboard/app.py` dan `dashboard/templates/dashboard_v5.html`

**Masalah:** Seismogram saat ini adalah animasi matematika murni (dummy). BMKG tidak menyediakan data waveform realtime publik.

**Yang harus dilakukan:**

**A. Tambah endpoint baru di `app.py`:**
```
GET /api/earthquakes/hourly
```
Return: jumlah gempa per jam dalam 24 jam terakhir, diambil dari tabel `earthquakes` dengan GROUP BY.

**B. Update frontend:** Ganti komponen `Seismogram` dengan komponen `EarthquakeChart` berupa bar chart SVG sederhana yang menampilkan data dari endpoint tersebut. Refresh setiap 5 menit. Label x-axis: jam (00–23), y-axis: jumlah gempa. Bar berwarna merah untuk jam yang ada gempa M≥5.

**Keuntungan:** Data ini 100% nyata dari DB, tidak ada animasi palsu, dan memberikan konteks historis yang berguna bagi operator.

---

## TAHAP 2 — SEDANG
> Estimasi: memerlukan beberapa sesi. Perubahan arsitektur frontend signifikan (routing antar halaman), penambahan integrasi eksternal, dan perubahan skema DB kecil.

---

### T2.1 — Sistem Routing Frontend (Bottom Nav Fungsional)

**File yang diubah:** `dashboard/templates/dashboard_v5.html`

**Konteks:** Bottom nav sudah ada dengan 7 tombol, tapi semua tombol tampilkan halaman yang sama karena tidak ada conditional rendering. Ini harus diperbaiki menjadi single-page app dengan 4 tab aktif.

**Desain navigasi baru (4 tab, buang yang tidak perlu):**

| Tab | Icon | Konten |
|---|---|---|
| **Monitor** | 📡 | Halaman utama saat ini: KPI + Peta + Chart + Feed |
| **Laporan** | 📄 | Daftar sitrep per gempa + draf komunikasi (4 bahasa) + coordination plan |
| **Antrean** | ✅ | Daftar draf yang menunggu persetujuan (expanded dari widget di Monitor) |
| **Log** | 📋 | Audit log semua aktivitas approve/reject/edit |

**Yang harus dilakukan:**
- Ubah state `nav` agar mengontrol komponen mana yang dirender
- Buat 4 komponen halaman terpisah: `PageMonitor`, `PageLaporan`, `PageAntrean`, `PageLog`
- Pindahkan semua logika fetching ke dalam masing-masing komponen halaman (jangan fetch data halaman yang tidak aktif)
- Komponen `PageMonitor` berisi kode dashboard yang sudah ada saat ini
- Badge pada tab "Antrean" menampilkan jumlah draf pending (dari `/api/approval/stats`)

**Catatan penting untuk operator saat darurat:** Tab "Antrean" harus paling mudah dijangkau. Pertimbangkan urutan: Monitor → Antrean → Laporan → Log.

---

### T2.2 — Peta Leaflet Interaktif dengan Daftar Titik Gempa

**File yang diubah:** `dashboard/templates/dashboard_v5.html`

**Konteks:** Peta Leaflet saat ini hanya menampilkan 1 marker (episenter gempa terbaru) dan 6 marker statis stasiun BMKG. Tidak ada interaksi dengan daftar gempa.

**Desain yang diinginkan:**
- Sebelah kiri: peta Leaflet penuh
- Sebelah kanan: panel daftar gempa (scrollable), menampilkan semua gempa dari DB (maks 50 terbaru)
- Setiap item di daftar menampilkan: magnitudo (dengan warna merah jika ≥5, kuning jika ≥3, abu jika <3), lokasi singkat, dan waktu relatif (misalnya "2 jam lalu")
- Klik item di daftar → peta fly/zoom ke koordinat gempa tersebut + buka popup dengan detail

**Data yang dibutuhkan:**
- Endpoint yang sudah ada: `GET /api/earthquakes?limit=50` → sudah return `latitude`, `longitude`, `magnitude`, `location_desc`, `timestamp`

**Yang harus dilakukan di frontend:**
1. Fetch `/api/earthquakes?limit=50` saat komponen `PageMonitor` mount
2. Render semua marker ke Leaflet dengan warna berbeda berdasarkan magnitudo:
   - M≥6: merah terang, icon besar, animasi pulse
   - M≥5: merah, icon sedang
   - M≥4: oranye, icon kecil
   - M<4: abu-abu, icon sangat kecil
3. Buat panel kanan (lebar ~280px) dengan daftar semua gempa yang sama
4. Klik item di panel → `map.flyTo([lat, lon], 9)` + `marker.openPopup()`
5. Klik marker di peta → highlight item yang sesuai di panel kanan (scroll into view)

**Tata letak:** Panel kanan bisa berupa `position: absolute; right: 0; top: 0; height: 100%` di atas `div#map`, dengan background semi-transparan dan `overflow-y: auto`.

---

### T2.3 — Halaman Login Operator

**File yang diubah:** `dashboard/app.py`, buat file baru `dashboard/templates/login.html`

**Konteks:** Saat ini tidak ada autentikasi sama sekali. Operator bisa langsung akses dashboard. Untuk BPBD, perlu ada login minimal untuk mencatat siapa yang melakukan approve/reject di audit log.

**Desain yang diinginkan:**
- Satu halaman login dengan form username + password
- Desain konsisten dengan dashboard: dark mode default, font Inter, warna --bg, --surface, --red
- Setelah login berhasil → redirect ke `GET /`
- Nama operator disimpan di Flask session
- Nama operator muncul di avatar (pojok kanan atas) dan di audit log saat approve/reject

**Implementasi di backend (`app.py`):**
1. Tambahkan list user hardcoded di `config.py` (cukup untuk MVP):
   ```python
   OPERATORS = {
       "admin": "password_bpbd_2025",
       "operator1": "gempa123",
   }
   ```
2. Tambahkan route `GET /login` → render `login.html`
3. Tambahkan route `POST /login` → validasi, set `session["operator"]`, redirect ke `/`
4. Tambahkan route `GET /logout` → clear session, redirect ke `/login`
5. Tambahkan decorator `@login_required` (buat fungsi helper) pada semua route yang butuh autentikasi
6. Di endpoint approve/reject: ganti hardcoded `"Petugas BPBD"` dengan `session.get("operator", "Petugas BPBD")`

**Desain `login.html`:** Halaman penuh dengan card di tengah, logo CEPAT di atas, form username/password, tombol login merah. Warna dan font sama persis dengan `dashboard_v5.html`.

---

### T2.4 — Halaman Laporan Lengkap (PageLaporan)

**File yang diubah:** `dashboard/templates/dashboard_v5.html`

**Konteks:** Hasil dari Analysis Agent (sitrep), Communication Agent (4 draf), dan Coordination Agent (rencana lapangan) saat ini tidak bisa dilihat dari dashboard utama. Hanya tersedia via API tapi tidak ada UI-nya.

**Desain halaman Laporan:**
- Daftar gempa M≥5 di sebelah kiri (panel, scrollable)
- Klik salah satu gempa → panel kanan menampilkan detail:
  - **Tab Situasi:** Situation Report (ringkasan, area terdampak, risk level, rekomendasi, generated_by)
  - **Tab Komunikasi:** 4 draf (Indonesia, Minang, Teknis, English) masing-masing dengan tombol **📋 Salin** (copy to clipboard)
  - **Tab Koordinasi:** Rencana koordinasi (resource mapping, 5 aksi prioritas P1/P2/P3, estimated timeline)

**Tombol Copy to Clipboard:**
```javascript
navigator.clipboard.writeText(content)
  .then(() => showToast("Disalin ke clipboard!"))
  .catch(() => showToast("Gagal menyalin"));
```
Toast notification kecil muncul di pojok kanan bawah selama 2 detik.

**Endpoint yang dibutuhkan (tambahkan ke `app.py`):**
- `GET /api/earthquakes/major` → list gempa M≥5 (sudah ada data, tinggal filter)
- `GET /api/laporan/<eq_id>` → return sitrep + drafts + coordination plan dalam satu response

**Endpoint `GET /api/laporan/<eq_id>` yang perlu dibuat:**
```python
@app.route("/api/laporan/<int:eq_id>")
def api_get_laporan(eq_id):
    sitrep = db.get_situation_report(eq_id)
    drafts = db.get_communication_drafts(eq_id)  # sudah ada
    plan   = db.get_coordination_plan(eq_id)     # sudah ada
    eq     = db.get_earthquake_by_id(eq_id)
    return jsonify({...})
```

---

### T2.5 — Bell Notifikasi Real

**File yang diubah:** `dashboard/templates/dashboard_v5.html`

**Desain:** Badge pada bell menampilkan jumlah `new_alerts` (gempa baru status NEW yang belum di-acknowledge) + jumlah `pending_drafts` (draf belum di-approve).

**Logika:**
- Data sudah tersedia dari `/api/stats` → field `new_alerts` (dari `db.get_stats()`) dan dari `/api/approval/stats` → field `pending_drafts`
- Total badge = `new_alerts + pending_drafts`
- Klik bell → dropdown kecil menampilkan list notifikasi singkat

**Dropdown notifikasi:**
- Item tipe "gempa baru": "⚠ Gempa M6.1 Pasaman Barat — 14:32 WIB" → klik → tab Monitor, zoom ke lokasi
- Item tipe "draf pending": "📄 3 draf menunggu persetujuan" → klik → tab Antrean

---

### T2.6 — Integrasi Telegram Channel Monitoring

**File yang diubah:** `agents/intelligence_agent.py`, `config.py`, `requirements.txt`

**Konteks:** Saat ini Intelligence Agent hanya scraping dari 4 RSS feed (ANTARA, Detik, Tribun, Google News). Tambahkan Telegram sebagai sumber tambahan via bot Telegram yang membaca pesan dari channel publik.

**Channel Telegram yang relevan:**
- `@infoBMKG` — channel resmi BMKG (update otomatis setiap ada gempa)
- `@BNPBIndonesia` — BNPB resmi
- `@InfoGempaBMKG` — khusus info gempa

**Cara implementasi (menggunakan `telethon` library):**

**A. Setup:**
- Tambahkan `telethon>=1.36.0` ke `requirements.txt`
- Tambahkan ke `config.py`:
  ```python
  TELEGRAM_API_ID     = os.getenv("TELEGRAM_API_ID", "")
  TELEGRAM_API_HASH   = os.getenv("TELEGRAM_API_HASH", "")
  TELEGRAM_CHANNELS   = ["infoBMKG", "BNPBIndonesia", "InfoGempaBMKG"]
  TELEGRAM_MAX_MSGS   = int(os.getenv("TELEGRAM_MAX_MSGS", 20))
  ```
- Tambahkan ke `.env.example`:
  ```
  TELEGRAM_API_ID=123456
  TELEGRAM_API_HASH=abcdef1234567890...
  ```
  (Diperoleh dari https://my.telegram.org/apps — gratis)

**B. Buat method baru di `intelligence_agent.py`:**
```python
def _fetch_telegram_messages(self) -> list[dict]:
    """Fetch pesan terbaru dari channel Telegram yang dikonfigurasi."""
    # Gunakan telethon dalam mode synchronous (asyncio.run)
    # Ambil maks TELEGRAM_MAX_MSGS pesan per channel
    # Filter berdasarkan EARTHQUAKE_KEYWORDS yang sama dengan RSS
    # Format output sama dengan artikel RSS: {source_name, source_url, title, content, published_at}
```

**C. Update method `_fetch_all_feeds()`:** Panggil `_fetch_telegram_messages()` dan gabungkan hasilnya dengan RSS sebelum filtering.

**Catatan:** Telethon butuh session file (autentikasi pertama kali via nomor HP). Simpan session di direktori `database/` agar persistent. Jika `TELEGRAM_API_ID` kosong, skip silently.

---

## TAHAP 3 — SULIT
> Estimasi: memerlukan banyak sesi dan pengujian menyeluruh. Perubahan arsitektur besar, integrasi eksternal kompleks, atau desain ulang komponen.

---

### T3.1 — Refaktor Frontend ke Multi-File (Opsional tapi Direkomendasikan)

**File yang dibuat:** Struktur baru atau tetap satu file tapi dengan organisasi lebih baik.

**Masalah saat ini:** `dashboard_v5.html` sudah 1906 baris dan akan terus bertambah. Sulit di-maintain.

**Opsi A (lebih mudah):** Tetap satu file HTML tapi pisahkan CSS ke `static/dashboard.css` dan JavaScript ke `static/dashboard.js`. Flask sudah siap melayani file statis.

**Opsi B (lebih baik jangka panjang):** Migrasi ke Vite + React project yang proper. Tapi ini butuh setup build pipeline dan mengubah cara deploy.

**Rekomendasi:** Pilih Opsi A dulu. Cukup pecah file tanpa mengubah arsitektur.

---

### T3.2 — Antrean Persetujuan dengan Halaman Detail Penuh

**File yang diubah:** `dashboard/templates/dashboard_v5.html` (komponen `PageAntrean`)

**Desain halaman Antrean yang lengkap:**
- Filter: Semua | Menunggu | Disetujui | Ditolak
- Setiap card menampilkan: tipe draf, preview konten, magnitudo gempa terkait, waktu masuk
- Klik card → expand / panel samping dengan konten draf penuh
- Tombol: Setujui, Tolak, Edit (dengan modal edit textarea)
- Untuk Coordination Plan: tampilkan 5 aksi prioritas dalam format tabel P1/P2/P3

**Widget di halaman Monitor** (setelah T2.1 selesai):
- Cukup tampilkan 5 draf terbaru dengan status
- Ada tombol "Lihat Semua →" yang navigate ke tab Antrean

---

### T3.3 — WebSocket Notifikasi Realtime

**File yang diubah:** `dashboard/app.py`, `dashboard/templates/dashboard_v5.html`, `requirements.txt`

**Kapan dibutuhkan:** Jika operator membutuhkan alert <5 detik setelah gempa terdeteksi (misalnya suara alarm).

**Implementasi dengan Flask-SocketIO:**
- Tambahkan `flask-socketio>=5.3.0` ke `requirements.txt`
- Di Orchestrator, setelah `monitoring_agent.poll_once()` menemukan gempa baru, emit event ke semua client yang terhubung
- Di frontend, subscribe ke event dan tampilkan toast alert + suara alarm opsional

**Event yang di-emit:**
```python
socketio.emit("new_earthquake", {
    "magnitude": eq["magnitude"],
    "location": eq["location_desc"],
    "id": eq["id"]
})
socketio.emit("pipeline_done", {
    "earthquake_id": eq_id,
    "drafts_count": len(drafts),
    "risk_level": sitrep["risk_level"]
})
```

**Catatan:** Ini mengubah cara menjalankan server — dari `app.run()` ke `socketio.run()`. Pastikan semua sudah stabil sebelum mengimplementasi ini.

---

### T3.4 — Sistem User Management yang Proper

**File yang diubah:** `database/schema.sql`, `database/db_handler.py`, `dashboard/app.py`, `config.py`

**Konteks:** T2.3 mengimplementasi login hardcoded. Tahap ini menggantinya dengan sistem user di DB.

**Tabel baru: `operators`**
```sql
CREATE TABLE IF NOT EXISTS operators (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,    -- bcrypt hash, JANGAN simpan plain text
    full_name   TEXT NOT NULL,
    role        TEXT DEFAULT 'operator',  -- 'admin' | 'operator' | 'viewer'
    is_active   INTEGER DEFAULT 1,
    last_login  TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Fitur:**
- Admin bisa tambah/nonaktifkan operator via halaman admin
- Password di-hash dengan `bcrypt` (`pip install bcrypt`)
- Role `viewer` bisa lihat tapi tidak bisa approve/reject
- Role `operator` bisa approve/reject tapi tidak bisa edit user
- Role `admin` akses penuh

---

### T3.5 — Export Laporan ke PDF

**Dependensi baru:** `weasyprint` atau `reportlab`

**Fitur:** Di halaman Laporan (T2.4), tambahkan tombol "Unduh PDF" yang generate PDF berisi:
- Header: logo CEPAT + BPBD + tanggal
- Data gempa (magnitudo, lokasi, kedalaman, koordinat)
- Situation Report lengkap
- 4 draf komunikasi
- Rencana koordinasi (5 aksi prioritas)
- Footer: nama operator yang login + timestamp generate

**Endpoint baru di `app.py`:**
```
GET /api/laporan/<eq_id>/pdf
```
Return: file PDF sebagai attachment.

---

### T3.6 — Dashboard Analytics & History

**File yang diubah:** Tambah komponen baru di `dashboard_v5.html`

**Fitur:**
- Grafik tren gempa 30 hari terakhir (line chart SVG)
- Peta heatmap frekuensi gempa per wilayah (warna makin merah = makin sering)
- Statistik: rata-rata magnitudo, total gempa per bulan, rasio gempa yang di-proses pipeline

**Endpoint baru di `app.py`:**
```
GET /api/analytics/monthly      # data per bulan
GET /api/analytics/heatmap      # data lat/lon count untuk heatmap
```

---

## Urutan Pengerjaan yang Direkomendasikan

```
T1.1 → T1.2 → T1.3 → T1.4      (selesaikan semua yang mudah dulu)
    ↓
T2.3 (Login)                     (keamanan penting sebelum ekspansi fitur)
    ↓
T2.1 (Routing nav)               (fondasi untuk semua halaman baru)
    ↓
T2.2 (Peta interaktif)           (bisa paralel dengan T2.4)
T2.4 (Halaman Laporan)           (bergantung pada T2.1)
    ↓
T2.5 (Bell notifikasi)           (bergantung pada T2.1)
T2.6 (Telegram)                  (independen, bisa kapan saja)
    ↓
T3.2 (Antrean lengkap)           (bergantung pada T2.1)
T3.3 (WebSocket)                 (opsional, hanya jika dibutuhkan)
T3.4 (User management)           (ganti T2.3 yang hardcoded)
T3.5 (Export PDF)                (fitur tambahan)
T3.6 (Analytics)                 (fitur tambahan)
```

---

## Hal-hal Penting untuk Diperhatikan

### Jangan Diubah Tanpa Alasan Kuat
- Struktur tabel DB yang sudah ada (tambah kolom boleh, jangan hapus/rename)
- Nama field di REST API yang sudah ada (frontend sudah bergantung padanya)
- Logika fallback di semua agent (jika LLM gagal, sistem harus tetap berjalan)
- Urutan pipeline di `orchestrator.py`: Monitoring → Intelligence → Analysis → Communication → Coordination

### Pattern yang Harus Diikuti
- Semua operasi DB menggunakan method di `db_handler.py` — jangan tulis query SQL langsung di agent atau app.py
- Semua konfigurasi (URL, threshold, timeout) harus ada di `config.py` yang membaca dari `.env`
- Semua agent harus punya fallback yang tidak bergantung pada LLM
- Error handling: gunakan `try/except` dan log dengan `logger.error()`, jangan biarkan exception mematikan server

### Variabel Lingkungan yang Perlu Ditambahkan ke `.env.example`
```
# Telegram (untuk T2.6)
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_MAX_MSGS=20

# Security (untuk T2.3)
FLASK_SECRET_KEY=ganti-dengan-string-acak-panjang
SESSION_LIFETIME_HOURS=8
```

---

## Checklist Verifikasi Setelah Selesai

Setelah setiap task selesai, verifikasi dengan:

- [ ] Server Flask bisa dijalankan tanpa error: `cd dashboard && python app.py`
- [ ] Semua endpoint API return status 200 dengan data yang benar
- [ ] Dashboard bisa dibuka di browser tanpa error di console
- [ ] Jika ada perubahan DB: jalankan dengan DB kosong untuk memastikan schema berjalan
- [ ] Jika ada perubahan agent: jalankan agent standalone (`python agents/namaagent.py`) untuk test
- [ ] Fallback tetap berfungsi saat `GEMINI_API_KEY` dikosongkan
