"""
demo_scenario.py — Skenario Demo CEPAT untuk Presentasi Juri
Gempa Pasaman Barat 2022 M 6.2 (data historis nyata)

Cara pakai:
    python tests/demo_scenario.py [--api | --no-api]

Mode:
    --api    : gunakan Gemini API untuk LLM (perlu GEMINI_API_KEY di .env)
    --no-api : jalankan semua pipeline dalam mode fallback (tanpa API key)

Alur skenario:
    1. Insert data gempa M 6.2 Pasaman Barat
    2. Insert 6 intelligence reports (5 valid + 1 hoax)
    3. Jalankan Analysis Agent → Situation Report
    4. Jalankan Communication Agent → 3 draf pesan
    5. Jalankan Coordination Agent → rencana koordinasi
    6. Tampilkan ringkasan semua output
"""

import sys
import os
import time
import argparse
import logging

# Tambahkan root project ke path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_handler import DatabaseHandler
from agents.analysis_agent import AnalysisAgent
from agents.communication_agent import CommunicationAgent
from agents.coordination_agent import CoordinationAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("DemoScenario")

# ─────────────────────────────────────────────────────────────
#  Data Demo — Gempa Pasaman Barat 2022
# ─────────────────────────────────────────────────────────────

DEMO_EARTHQUAKE = {
    "event_id":          "demo-pasaman-2022-02-25",
    "magnitude":         6.2,
    "depth_km":          10.0,
    "latitude":          0.097,
    "longitude":         99.943,
    "location_desc":     "14 km BaratLaut PASABAR-SUMBAR",
    "timestamp":         "2022-02-25T08:39:00+07:00",
    "felt_area":         "Pasaman Barat, Pasaman, Agam, Bukittinggi",
    "tsunami_potential": "Tidak berpotensi tsunami",
    "pipeline_status":   "PENDING",
}

DEMO_INTEL_REPORTS = [
    {
        "source_name":        "ANTARA",
        "source_url":         "https://www.antaranews.com/berita/gempa-pasaman-2022",
        "source_type":        "news_rss",
        "title":              "Gempa M6.2 Guncang Pasaman Barat, Warga Berhamburan Keluar Rumah",
        "content":            "BMKG melaporkan gempa berkekuatan M6.2 mengguncang Pasaman Barat, Sumatera Barat pada Jumat (25/2) pukul 08.39 WIB. Pusat gempa berada di 14 km barat laut Pasaman Barat dengan kedalaman 10 km. Warga melaporkan rumah dan bangunan rusak. BPBD Pasaman Barat telah menurunkan tim ke lapangan.",
        "credibility_status": "VALID",
        "llm_reasoning":      "Sumber terpercaya (ANTARA), data konsisten dengan BMKG, ada detail spesifik lokasi dan waktu.",
    },
    {
        "source_name":        "Detik",
        "source_url":         "https://news.detik.com/berita/gempa-pasaman-6-2",
        "source_type":        "news_rss",
        "title":              "Update Gempa Pasaman: 3 Kecamatan Rusak Parah, Evakuasi Dimulai",
        "content":            "Tiga kecamatan di Pasaman Barat dilaporkan mengalami kerusakan parah akibat gempa M6.2. BPBD Pasaman Barat mencatat ratusan rumah rusak. Tim SAR telah diturunkan untuk melakukan evakuasi dan pencarian korban di bawah reruntuhan. Akses jalan menuju beberapa desa terputus akibat longsor.",
        "credibility_status": "VALID",
        "llm_reasoning":      "Sumber resmi (Detik), laporan evakuasi konsisten dengan magnitude gempa, informasi detail dan spesifik.",
    },
    {
        "source_name":        "Tribun",
        "source_url":         "https://www.tribunnews.com/gempa-pasaman-korban",
        "source_type":        "news_rss",
        "title":              "25 Korban Luka Gempa Pasaman, Rumah Sakit Kewalahan",
        "content":            "Dinas Kesehatan Pasaman Barat mencatat 25 korban luka akibat gempa M6.2. Rumah sakit setempat kewalahan menangani pasien. Pemerintah provinsi Sumatera Barat telah mengirimkan tim medis tambahan dan logistik bantuan darurat.",
        "credibility_status": "VALID",
        "llm_reasoning":      "Data korban spesifik dan realistis untuk gempa M6.2, sumber terpercaya, ada respon pemerintah.",
    },
    {
        "source_name":        "GNews",
        "source_url":         "https://news.google.com/gempa-pasaman-2022-tsunami",
        "source_type":        "google_news",
        "title":              "Gempa Pasaman Picu Tsunami 10 Meter, 1000 Korban Jiwa",
        "content":            "Gempa dahsyat M8.9 mengguncang Pasaman Barat memicu tsunami setinggi 10 meter. Lebih dari 1000 orang dilaporkan tewas. Seluruh kota Pasaman tenggelam.",
        "credibility_status": "HOAX",
        "llm_reasoning":      "Informasi palsu — BMKG tidak melaporkan tsunami, magnitudo berbeda jauh (M8.9 vs M6.2 aktual), jumlah korban tidak realistis dan bertentangan data resmi.",
    },
    {
        "source_name":        "Twitter/X",
        "source_url":         "https://twitter.com/warga_pasaman/status/demo",
        "source_type":        "twitter",
        "title":              "Laporan warga: jembatan di Kecamatan Talamau putus",
        "content":            "Warga melaporkan jembatan penghubung di Kecamatan Talamau, Pasaman Barat putus akibat gempa. Akses ke beberapa desa terisolir. Mohon bantuan segera. #GempaPasaman #BPBD",
        "credibility_status": "UNVERIFIED",
        "llm_reasoning":      "Laporan warga belum bisa diverifikasi, informasi parsial, perlu konfirmasi dari BPBD lapangan.",
    },
    {
        "source_name":        "ANTARA",
        "source_url":         "https://www.antaranews.com/gempa-pasaman-aftershock",
        "source_type":        "news_rss",
        "title":              "BMKG Catat 5 Gempa Susulan Pasca Gempa Utama Pasaman M6.2",
        "content":            "BMKG mencatat lima kali gempa susulan setelah gempa utama M6.2 di Pasaman Barat. Gempa susulan terbesar M4.7. BMKG mengimbau warga tetap waspada dan menghindari bangunan rusak.",
        "credibility_status": "VALID",
        "llm_reasoning":      "Sumber BMKG/ANTARA resmi, aftershock pasca gempa M6.2 adalah normal secara ilmiah, data spesifik dan konsisten.",
    },
]

# ─────────────────────────────────────────────────────────────
#  Helper
# ─────────────────────────────────────────────────────────────

def separator(title: str):
    width = 60
    print("\n" + "=" * width)
    pad = (width - len(title) - 2) // 2
    print(f"{'='*pad} {title} {'='*pad}")
    print("=" * width)


def print_section(label: str, content: str):
    print(f"\n  >> {label}:")
    for line in content.splitlines():
        print(f"      {line}")


# ─────────────────────────────────────────────────────────────
#  Skenario Utama
# ─────────────────────────────────────────────────────────────

def run_demo(use_api: bool = False):
    if not use_api:
        # Nonaktifkan API key agar fallback digunakan
        os.environ["GEMINI_API_KEY"] = ""

    separator("DEMO CEPAT - Gempa Pasaman Barat 2022 M6.2")
    print(f"  Mode: {'LLM (Gemini API)' if use_api else 'Fallback (tanpa API)'}")
    print(f"  Database: {os.path.abspath('database/cepat.db')}")

    # ── Step 0: Inisialisasi ────────────────────────────────
    separator("Step 0 - Inisialisasi Database")
    db = DatabaseHandler()
    print("  [OK] Database siap")

    # ── Step 1: Insert Gempa ────────────────────────────────
    separator("Step 1 - Monitoring Agent: Data Gempa BMKG")
    existing = None
    with db._connect() as conn:
        row = conn.execute("SELECT * FROM earthquakes WHERE event_id=?", (DEMO_EARTHQUAKE["event_id"],)).fetchone()
        if row:
            existing = dict(row)

    if existing:
        eq_id = existing["id"]
        print(f"  [OK] Gempa sudah ada di database (ID={eq_id})")
        db.update_pipeline_status(eq_id, "PENDING")
        print(f"  [OK] Pipeline status di-reset ke PENDING")
    else:
        db.insert_earthquake(DEMO_EARTHQUAKE)
        with db._connect() as conn:
            row = conn.execute("SELECT * FROM earthquakes WHERE event_id=?", (DEMO_EARTHQUAKE["event_id"],)).fetchone()
        eq_id = dict(row)["id"]
        print(f"  [OK] Gempa baru diinsert (ID={eq_id})")

    eq = db.get_earthquake_by_id(eq_id)
    print(f"  Gempa   : M{eq['magnitude']} | {eq['location_desc']}")
    print(f"  Waktu   : {eq['timestamp']}")
    print(f"  Dirasakan: {eq['felt_area']}")

    # ── Step 2: Insert Intelligence Reports ─────────────────
    separator("Step 2 - Intelligence Agent: Laporan Media")
    with db._connect() as conn:
        existing_intel = conn.execute(
            "SELECT COUNT(*) FROM intelligence_reports WHERE earthquake_id=?", (eq_id,)
        ).fetchone()[0]

    if existing_intel == 0:
        for report in DEMO_INTEL_REPORTS:
            report["earthquake_id"] = eq_id
            db.insert_intelligence_report(report)
        print(f"  [OK] {len(DEMO_INTEL_REPORTS)} intelligence reports diinsert")
    else:
        print(f"  [OK] {existing_intel} intelligence reports sudah ada (skip insert)")

    intel = db.get_intelligence_reports(eq_id)
    valid_count = sum(1 for r in intel if r["credibility_status"] == "VALID")
    hoax_count  = sum(1 for r in intel if r["credibility_status"] == "HOAX")
    unverified  = sum(1 for r in intel if r["credibility_status"] == "UNVERIFIED")
    print(f"  Laporan: {len(intel)} total | [V] {valid_count} VALID | [H] {hoax_count} HOAX | [?] {unverified} UNVERIFIED")
    for r in intel:
        icon = {"VALID":"V","HOAX":"H","UNVERIFIED":"?"}.get(r["credibility_status"], "?")
        print(f"    [{icon}] {r['source_name']:8} | {r['title'][:60]}")

    # ── Step 3: Analysis Agent ───────────────────────────────
    separator("Step 3 - Analysis Agent: Situation Report")
    analysis_agent = AnalysisAgent(db_handler=db)
    sitrep = analysis_agent.run(eq_id)

    if sitrep:
        print(f"  [OK] Situation Report dibuat (generated_by={sitrep.get('generated_by')})")
        print_section("Risk Level",    sitrep.get("risk_level", "-"))
        print_section("Ringkasan",     sitrep.get("summary", "-"))
        print_section("Wilayah",       sitrep.get("affected_areas", "-"))
        print_section("Justifikasi",   sitrep.get("risk_justification", "-"))
        recs = sitrep.get("recommendations", [])
        if recs:
            print("\n  >> Rekomendasi:")
            for i, r in enumerate(recs, 1):
                print(f"      {i}. {r}")
    else:
        print("  [GAGAL] Situation Report tidak dibuat!")
        return

    # ── Step 4: Communication Agent ─────────────────────────
    separator("Step 4 - Communication Agent: Draf Pesan Alert")
    comm_agent = CommunicationAgent(db_handler=db)
    with db._connect() as conn:
        conn.execute("DELETE FROM communication_drafts WHERE earthquake_id=?", (eq_id,))
    drafts = comm_agent.run(eq_id)

    print(f"  [OK] {len(drafts)} draf pesan dibuat")
    for d in drafts:
        label = {"public_id":"Alert Publik (ID)","public_minang":"Alert Minang","technical":"Laporan Teknis"}.get(d["draft_type"], d["draft_type"])
        print(f"\n  [{label}]")
        content_lines = d["content"].splitlines()
        for line in content_lines[:5]:
            print(f"    {line}")
        if len(content_lines) > 5:
            print(f"    ... (+{len(content_lines)-5} baris)")

    # ── Step 5: Coordination Agent ───────────────────────────
    separator("Step 5 - Coordination Agent: Rencana Koordinasi")
    coord_agent = CoordinationAgent(db_handler=db)
    with db._connect() as conn:
        conn.execute("DELETE FROM coordination_plans WHERE earthquake_id=?", (eq_id,))
    plan = coord_agent.run(eq_id)

    if plan:
        print(f"  [OK] Rencana koordinasi dibuat (generated_by={plan.get('generated_by')})")
        print_section("Mapping Sumber Daya", plan.get("resource_mapping", "-")[:300])
        print(f"\n  >> Aksi Prioritas ({len(plan.get('action_priorities', []))} aksi):")
        for a in plan.get("action_priorities", []):
            print(f"      [{a.get('priority','?')}] Jam+{a.get('timeline_hours','?')}j - {a.get('action','-')}: {a.get('description','-')[:80]}")
        print_section("Estimasi Timeline", plan.get("estimated_timeline", "-"))
    else:
        print("  [GAGAL] Rencana koordinasi tidak dibuat!")

    # ── Step 6: Status Approval Queue ───────────────────────
    separator("Step 6 - Human-in-the-Loop: Approval Queue")
    stats = db.get_approval_stats()
    print(f"  Menunggu approval petugas:")
    print(f"    - Draf pesan   : {stats['pending_drafts']} item")
    print(f"    - Rencana koor : {stats['pending_plans']} item")
    print(f"    - Total pending: {stats['total_pending']} item")
    print("  Buka dashboard di: http://localhost:5000/")
    print("  Petugas dapat: [OK] Setujui / [E] Edit / [X] Tolak setiap item di tab 'Queue'")

    # ── Ringkasan ────────────────────────────────────────────
    separator("RINGKASAN DEMO")
    print(f"  [OK] Gempa            : M{eq['magnitude']} {eq['location_desc']}")
    print(f"  [OK] Intel reports    : {len(intel)} ({valid_count} valid, {hoax_count} hoax, {unverified} unverified)")
    print(f"  [OK] Situation Report : RISK={sitrep.get('risk_level')} ({sitrep.get('generated_by')})")
    print(f"  [OK] Draf pesan       : {len(drafts)}/3 dibuat")
    print(f"  [OK] Rencana koordinasi: {'OK' if plan else 'GAGAL'}")
    print(f"  [OK] Approval pending : {stats['total_pending']} item")
    print("  [>>] Jalankan dashboard: python dashboard/app.py")
    print("  [>>] Buka browser     : http://localhost:5000")
    print("  [>>] Dashboard & Queue: http://localhost:5000/ (Pilih tab 'Queue' di bawah)")
    print()

    return {
        "eq_id":   eq_id,
        "sitrep":  sitrep,
        "drafts":  drafts,
        "plan":    plan,
        "stats":   stats,
    }


# ─────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CEPAT Demo Scenario — Gempa Pasaman Barat 2022")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--api",    action="store_true", help="Gunakan Gemini API (perlu GEMINI_API_KEY)")
    group.add_argument("--no-api", action="store_true", help="Jalankan dalam mode fallback (tanpa API)")
    args = parser.parse_args()

    use_api = args.api  # Default: no-api (fallback mode)

    if use_api:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key or api_key.startswith("AIza..."):
            print("ERROR: GEMINI_API_KEY tidak diset di .env")
            print("       Jalankan dengan --no-api untuk mode fallback")
            sys.exit(1)

    result = run_demo(use_api=use_api)
