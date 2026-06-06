# CEPAT — Penjelasan Lengkap

---

## Apa itu CEPAT?

CEPAT adalah **sistem multi-agent AI** yang membantu **petugas BPBD** (Badan Penanggulangan Bencana Daerah — semacam "Dinas Bencana" di tingkat kota/kabupaten) saat gempa terjadi.

**Masalah yang diselesaikan:**
Saat gempa, petugas BPBD harus memantau banyak hal sekaligus dalam waktu singkat:
- Data resmi dari BMKG (Badan Meteorologi, Klimatologi, Geofisika)
- Berita dari media online
- Laporan dari lapangan
- Memutuskan apa yang harus dilakukan

Semua itu dilakukan **manual**, sehingga lambat dan rawan salah.

CEPAT menggantikan pekerjaan manual itu dengan **5 agen AI yang bekerja paralel**, lalu menyajikan hasilnya ke petugas untuk di-review dan disetujui.

---

## Istilah Penting

| Istilah | Penjelasan Sederhana |
|---|---|
| **BMKG** | Lembaga pemerintah yang mengukur dan melaporkan gempa secara resmi. CEPAT mengambil data langsung dari API mereka. |
| **Magnitudo (M)** | Ukuran kekuatan gempa. M5 = terasa kuat, M6 = merusak, M7+ = bisa sangat merusak. |
| **BPBD** | "Dinas Bencana" di tingkat kota/kabupaten. Mereka yang pertama merespons saat bencana. |
| **BNPB** | Versi nasionalnya BPBD (Badan Nasional Penanggulangan Bencana). |
| **Sitrep** | *Situation Report* — laporan ringkasan situasi darurat: apa yang terjadi, seberapa parah, apa yang harus dilakukan. |
| **Hoax filter** | Penyaring berita bohong. AI membaca berita dan memutuskan: ini benar (VALID), palsu (HOAX), atau belum terkonfirmasi (UNVERIFIED). |
| **Risk level** | Tingkat risiko bencana: LOW (rendah) → MEDIUM → HIGH → CRITICAL (paling berbahaya). |
| **Human-in-the-loop** | Artinya: **manusia tetap memegang kendali**. AI hanya menyiapkan, petugas yang memutuskan apakah output AI disetujui atau tidak. |
| **Pipeline** | Urutan proses yang berjalan otomatis: Gempa terdeteksi → berita dikumpulkan → sitrep dibuat → pesan disiapkan → rencana dibuat. |

---

## 5 Agen AI dalam CEPAT

```
BMKG API ──► [1. MONITORING]
                    │
                    ▼
Berita/RSS ──► [2. INTELLIGENCE] → Hoax filter
                    │
                    ▼
              [3. ANALYSIS] → Situation Report
                    │
           ┌────────┴────────┐
           ▼                 ▼
    [4. COMMUNICATION]  [5. COORDINATION]
    (Draf pesan alert)  (Rencana lapangan)
           │                 │
           └────────┬────────┘
                    ▼
          DASHBOARD PETUGAS
          (Review → Approve)
```

**Agen 1 — Monitoring Agent**
Setiap 5 menit, otomatis mengambil data gempa terbaru dari BMKG. Jika ada gempa M≥5, langsung masuk ke sistem dan memicu agen berikutnya.

**Agen 2 — Intelligence Agent**
Mengumpulkan berita dari RSS feed media nasional (Antara, Detik, Tribun, Google News) serta Telegram channel tanggap bencana. Lalu menggunakan Google Gemini AI untuk menilai setiap berita: apakah **VALID**, **HOAX**, atau **UNVERIFIED**. Ini penting karena saat bencana banyak info palsu beredar di media sosial.

**Agen 3 — Analysis Agent**
Menggabungkan data BMKG + berita yang sudah difilter, lalu menulis **Situation Report** — dokumen ringkasan yang berisi: apa yang terjadi, wilayah mana yang terdampak, seberapa parah risikonya, dan apa yang harus dilakukan. Ini yang biasanya dikerjakan analis BPBD secara manual dalam 30–60 menit.

**Agen 4 — Communication Agent**
Berdasarkan Situation Report, membuat 3 versi pesan siap kirim:
- **Alert Publik** (Bahasa Indonesia, maks 160 karakter) → untuk broadcast ke warga via WhatsApp/SMS
- **Alert Bahasa Minang** → khusus komunitas Sumatera Barat
- **Laporan Teknis** → untuk koordinasi dengan TNI, Polri, BASARNAS

**Agen 5 — Coordination Agent**
Membuat **rencana koordinasi lapangan**: sumber daya apa yang tersedia, 5 aksi yang harus dilakukan (diprioritaskan P1/P2/P3), dan estimasi waktunya.

---

## Alur Demo Step-by-Step

**Skenario:** Gempa Pasaman Barat 2022, M6.2 — peristiwa nyata yang pernah terjadi.

---

### Step 1 — Data Gempa Masuk

Script memasukkan data gempa ke sistem:
- Magnitudo: **M6.2**
- Lokasi: 14 km Barat Laut Pasaman Barat, Sumatera Barat
- Kedalaman: 10 km (dangkal = lebih merusak)
- Dirasakan di: Pasaman Barat, Pasaman, Agam, Bukittinggi

Di dashboard, ini akan muncul sebagai titik merah di peta dan baris di tabel gempa.

---

### Step 2 — Berita Dikumpulkan & Difilter

6 laporan berita dimasukkan ke sistem (simulasi hasil scraping):

| No | Sumber | Judul (singkat) | Status |
|---|---|---|---|
| 1 | ANTARA | Gempa M6.2 guncang Pasaman Barat | ✅ VALID |
| 2 | Detik | 3 kecamatan rusak parah, evakuasi dimulai | ✅ VALID |
| 3 | Tribun | 25 korban luka, RS kewalahan | ✅ VALID |
| 4 | GNews | **Gempa picu tsunami 10m, 1000 korban** | ❌ HOAX |
| 5 | Twitter | Jembatan Talamau putus (laporan warga) | ❓ UNVERIFIED |
| 6 | ANTARA | BMKG catat 5 gempa susulan | ✅ VALID |

Berita nomor 4 sengaja dibuat hoax — melebih-lebihkan angka agar AI bisa mendeteksinya.

---

### Step 3 — Situation Report Dibuat

AI menghasilkan dokumen sitrep yang berisi:
- **Risk Level: HIGH** (karena M6.2,n kedalaman dagkal)
- Ringkasan kejadian
- Estimasi wilayah terdampak
- 5 rekomendasi tindakan prioritas

Tanpa Gemini API, sitrep dibuat dengan aturan bawaan (fallback). Dengan Gemini API, sitrep lebih detail dan kontekstual.

---

### Step 4 — 3 Draf Pesan Dibuat

Contoh output fallback:

**Alert Publik (160 karakter):**
> GEMPA M6.2 14 km BaratLaut PASABAR-SUMBAR. Risiko TINGGI. Ikuti arahan BPBD. Jauhi bangunan rusak.

**Alert Bahasa Minang:**
> GEMPA BUMI M6.2 di Pasaman Barat. Ikolah imbauan BPBD, jauahi bangunan nan rusak, jan panik. Tingkek risiko: TINGGI.

**Laporan Teknis (untuk instansi):**
> LAPORAN TEKNIS — BPBD. Gempa: M6.2 SR | Lokasi: ... | Risk Level: HIGH | ...

Semua draf ini **BELUM dikirim** — masih menunggu persetujuan petugas.

---

### Step 5 — Rencana Koordinasi Dibuat

5 aksi yang harus dilakukan, urut prioritas:

| Prioritas | Waktu | Aksi |
|---|---|---|
| **P1** | Jam ke-1 | Aktifkan Status Siaga II, kerahkan tim BPBD |
| **P1** | Jam ke-2 | Tim SAR asesmen lapangan, cari korban |
| **P2** | Jam ke-4 | Dirikan tenda pengungsian, distribusi logistik |
| **P2** | Jam ke-6 | Aktifkan pos medis lapangan |
| **P3** | Jam ke-12 | Pendataan warga terdampak, pemulihan infrastruktur |

---

### Step 6 — Approval Queue (Inti dari Human-in-the-Loop)

Semua output agen masuk ke **antrian persetujuan**. Petugas BPBD membuka tab **Queue** di dashboard utama dan bisa:

- ✅ **Setujui** — item ditandai APPROVED, tercatat di audit log
- ✏️ **Edit** — petugas bisa mengubah isi pesan sebelum menyetujui (misal: koreksi nama desa)
- ❌ **Tolak** — petugas menolak dengan alasan (tercatat di audit log)

Ini penting: **AI tidak pernah langsung mengirim pesan ke publik**. Semua harus melalui persetujuan manusia.

---

## Cara Menjalankan

### 1. Jalankan Demo Scenario (no-api)

```bash
cd C:\Users\MBN0C\Downloads\CEPAT
python tests/demo_scenario.py --no-api
```

### 2. Jalankan Dashboard

```bash
python dashboard/app.py
```

Lalu buka browser:

| Dashboard utama (termasuk Queue) | `http://localhost:5000` |

### 3. Demo dengan Gemini API (opsional)

1. Buat file `.env` dari template:
   ```bash
   copy .env.example .env
   ```
2. Edit `.env`, isi `GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxx`
3. Jalankan:
   ```bash
   python tests/demo_scenario.py --api
   ```

---

## Mengapa Ini Berguna untuk Demo ke Juri?

**Sebelum CEPAT:** Petugas BPBD butuh 30–60 menit untuk mengumpulkan info, menulis sitrep, dan menyiapkan pesan — semuanya manual.

**Dengan CEPAT:** Dalam **< 3 menit**, sistem sudah menyiapkan sitrep, 3 draf pesan, dan rencana koordinasi. Petugas tinggal review dan klik setujui.

**Yang perlu ditekankan ke juri:**
1. Data BMKG **real** (bukan simulasi) — bisa dicek live
2. Hoax filter **aktif** — AI bisa bedakan berita valid vs hoax
3. **Human tetap memegang kendali** — semua keputusan ada di tangan petugas
4. Sistem **graceful degradation** — tanpa API key pun tetap berjalan (fallback mode)
5. Arsitektur **multi-agent** — setiap agen punya tugas spesifik, bekerja paralel, koordinasi via Orchestrator
