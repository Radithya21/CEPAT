"""
demo_expo.py — CEPAT Expo Demo Script
Script khusus untuk demonstrasi di expo/lomba internasional.

Cara pakai:
    python demo_expo.py              # Gunakan data gempa terbaru dari DB
    python demo_expo.py --simulate   # Simulasikan skenario gempa demo (tidak butuh internet)
    python demo_expo.py --status     # Cek status semua provider LLM

Fitur:
- Auto-detect provider aktif (Groq / Ollama / Fallback)
- Visual progress bar step-by-step
- Output 4 bahasa dengan layout rapi
- Mode simulate: skenario gempa hardcoded untuk demo tanpa data live
"""

import sys
import os
import time
import logging
import argparse
from datetime import datetime

# Tambahkan root project ke path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────
#  ANSI Colors (terminal visual)
# ─────────────────────────────────────────────────────────────
RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
MAGENTA= "\033[95m"
CYAN   = "\033[96m"
WHITE  = "\033[97m"
BG_RED = "\033[41m"
BG_BLUE= "\033[44m"

# ─────────────────────────────────────────────────────────────
#  Logging Setup
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.WARNING,  # Suppress agent logs untuk tampilan bersih
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
)

# ─────────────────────────────────────────────────────────────
#  Skenario Demo (Hardcoded untuk mode --simulate)
# ─────────────────────────────────────────────────────────────
DEMO_EARTHQUAKE = {
    "id": 9999,
    "magnitude": 6.5,
    "location_desc": "87 km BaratDaya KEPULAUAN MENTAWAI-SUMBAR",
    "depth_km": 12.0,
    "latitude": -2.45,
    "longitude": 99.32,
    "timestamp": datetime.now().isoformat(),
    "tsunami_potential": "Gempa ini BERPOTENSI TSUNAMI",
    "felt_area": "Padang, Pariaman, Painan, Sijunjung",
    "pipeline_status": "PENDING",
    "source": "DEMO",
}


# ─────────────────────────────────────────────────────────────
#  Helper: Print Functions
# ─────────────────────────────────────────────────────────────

def _divider(char="─", width=65, color=DIM):
    print(f"{color}{char * width}{RESET}")


def _header(text: str, color=CYAN):
    width = 65
    pad = (width - len(text) - 2) // 2
    print(f"\n{color}{BOLD}{'═' * width}{RESET}")
    print(f"{color}{BOLD}{'═' * pad} {text} {'═' * pad}{RESET}")
    print(f"{color}{BOLD}{'═' * width}{RESET}\n")


def _step(num: int, total: int, name: str, status: str = "RUNNING"):
    colors = {"RUNNING": YELLOW, "DONE": GREEN, "FAILED": RED, "SKIP": DIM}
    icons  = {"RUNNING": "⟳", "DONE": "✔", "FAILED": "✘", "SKIP": "–"}
    c = colors.get(status, WHITE)
    i = icons.get(status, "?")
    print(f"  {c}{BOLD}[{i}] Step {num}/{total}: {name}{RESET}")


def _print_provider_status(status: dict):
    groq_ok   = status.get("groq_available")
    ollama_ok = status.get("ollama_available")
    last      = status.get("last_provider", "none")

    print(f"\n  {BOLD}🔌 LLM Provider Status:{RESET}")
    groq_icon   = f"{GREEN}✔ READY" if groq_ok   else f"{RED}✘ No Key"
    ollama_icon = f"{GREEN}✔ READY" if ollama_ok else f"{YELLOW}⚠ Offline"
    print(f"     Groq   [{status.get('groq_model', '?')}] : {groq_icon}{RESET}")
    print(f"     Ollama [{status.get('ollama_model', '?')}] : {ollama_icon}{RESET}")
    if last != "none":
        print(f"     Last used: {CYAN}{last.upper()}{RESET}")
    print()


def _print_earthquake(eq: dict):
    mag = eq.get("magnitude", "?")
    loc = eq.get("location_desc", "?")
    dep = eq.get("depth_km", "?")
    ts  = eq.get("timestamp", "?")
    try:
        ts = datetime.fromisoformat(str(ts)).strftime("%d %b %Y %H:%M WIB")
    except Exception:
        pass

    tsunami = eq.get("tsunami_potential", "")
    tsunami_flag = f"{RED}{BOLD}⚠ TSUNAMI POTENTIAL{RESET}" if "berpotensi" in tsunami.lower() and "tidak" not in tsunami.lower() else f"{GREEN}✔ No tsunami threat{RESET}"

    risk_color = {6.5: RED, 6.0: YELLOW, 5.0: YELLOW}.get(mag, GREEN)

    print(f"  {BOLD}Magnitude  :{RESET} {risk_color}{BOLD}M{mag}{RESET}")
    print(f"  {BOLD}Location   :{RESET} {WHITE}{loc}{RESET}")
    print(f"  {BOLD}Depth      :{RESET} {dep} km")
    print(f"  {BOLD}Time       :{RESET} {ts}")
    print(f"  {BOLD}Felt in    :{RESET} {eq.get('felt_area', '—')}")
    print(f"  {BOLD}Tsunami    :{RESET} {tsunami_flag}")


def _print_multilang_output(drafts: list[dict]):
    """Print output 4 bahasa dengan layout rapi."""
    draft_map = {d["draft_type"]: d["content"] for d in drafts}

    labels = [
        ("public_id",     "🇮🇩", "INDONESIA (Publik)"),
        ("english",       "🇬🇧", "ENGLISH (Public Alert)"),
        ("technical",     "⚙️ ", "TECHNICAL REPORT (English)"),
        ("public_minang", "🏔️ ", "BAHASA MINANG (Lokal)"),
    ]

    for key, flag, label in labels:
        content = draft_map.get(key, "")
        if not content:
            continue
        print(f"\n  {flag} {BOLD}{CYAN}{label}{RESET}")
        _divider("·", 63, DIM)
        # Word wrap untuk terminal
        words = content.split()
        line = "  "
        for word in words:
            if len(line) + len(word) + 1 > 67:
                print(f"{WHITE}{line}{RESET}")
                line = "  " + word + " "
            else:
                line += word + " "
        if line.strip():
            print(f"{WHITE}{line}{RESET}")


def _animated_wait(seconds: float, label: str = "Processing"):
    """Loading animation sambil tunggu LLM."""
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    end_time = time.time() + seconds
    i = 0
    while time.time() < end_time:
        frame = frames[i % len(frames)]
        print(f"\r  {CYAN}{frame} {label}...{RESET}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    print(f"\r  {GREEN}✔ Done!{' ' * 30}{RESET}")


# ─────────────────────────────────────────────────────────────
#  Mode: Status Check
# ─────────────────────────────────────────────────────────────

def cmd_status():
    _header("CEPAT — LLM Provider Status Check")
    from utils.llm_client import LLMClient
    client = LLMClient()
    status = client.get_status()
    _print_provider_status(status)

    print(f"  {BOLD}Testing Groq API...{RESET}")
    result = client._generate_groq("Say 'CEPAT system online' in one sentence.", max_tokens=50)
    if result:
        print(f"  {GREEN}✔ Groq OK:{RESET} {result[:80]}")
    else:
        print(f"  {RED}✘ Groq FAILED{RESET}")

    if status.get("ollama_available"):
        print(f"\n  {BOLD}Testing Ollama...{RESET}")
        result_ol = client._generate_ollama("Say 'Ollama ready' in one sentence.", max_tokens=30)
        if result_ol:
            print(f"  {GREEN}✔ Ollama OK:{RESET} {result_ol[:80]}")
        else:
            print(f"  {RED}✘ Ollama FAILED{RESET}")

    _divider()
    print(f"\n  {GREEN}Status check selesai.{RESET}\n")


# ─────────────────────────────────────────────────────────────
#  Mode: Full Pipeline Demo
# ─────────────────────────────────────────────────────────────

def run_demo(simulate: bool = False):
    _header("CEPAT — AI Orchestrator Demo", CYAN)
    print(f"  {DIM}CEPAT: Centralized Emergency Prediction and Alert Technology{RESET}")
    print(f"  {DIM}AI-Powered Earthquake Response Orchestrator — Expo Demo Mode{RESET}\n")

    # ── Import Agents ──────────────────────────────────────────
    print(f"  {BOLD}🔄 Initializing AI Agents...{RESET}")
    from utils.llm_client import LLMClient
    from database.db_handler import DatabaseHandler
    from agents.analysis_agent import AnalysisAgent
    from agents.communication_agent import CommunicationAgent
    from agents.coordination_agent import CoordinationAgent

    db      = DatabaseHandler()
    llm     = LLMClient()
    analyst = AnalysisAgent(db_handler=db)
    comm    = CommunicationAgent(db_handler=db)
    coord   = CoordinationAgent(db_handler=db)

    _print_provider_status(llm.get_status())

    # ── Get Earthquake Data ────────────────────────────────────
    if simulate:
        print(f"  {MAGENTA}{BOLD}🎭 SIMULATION MODE — Skenario Gempa Demo{RESET}")
        earthquake = DEMO_EARTHQUAKE

        # Insert ke DB untuk pipeline
        eq_id = db.insert_earthquake(earthquake)
        if not eq_id:
            # Coba ambil yang sudah ada dengan ID 9999
            existing = db.get_earthquake_by_id(9999)
            if existing:
                eq_id = 9999
                earthquake = existing
            else:
                print(f"  {RED}Gagal menyimpan data demo ke database.{RESET}")
                return
        else:
            earthquake["id"] = eq_id
    else:
        print(f"  {BOLD}📡 Mengambil data gempa terbaru dari database...{RESET}")
        from agents.monitoring_agent import MonitoringAgent
        monitor = MonitoringAgent(db_handler=db)
        try:
            monitor.poll_once()
        except Exception as e:
            print(f"  {YELLOW}⚠ Poll BMKG gagal: {e} — coba data dari DB{RESET}")

        # Ambil gempa terbaru dari DB
        pending = db.get_pending_earthquakes(min_magnitude=5.0)
        if not pending:
            # Ambil gempa terakhir apapun statusnya
            from database.db_handler import DatabaseHandler as DB
            import sqlite3
            conn = sqlite3.connect(db.db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM earthquakes ORDER BY id DESC LIMIT 1"
            ).fetchone()
            conn.close()
            if row:
                earthquake = dict(row)
                eq_id = earthquake["id"]
                # Reset status agar bisa diproses ulang
                db.update_pipeline_status(eq_id, "PENDING")
            else:
                print(f"  {RED}Tidak ada data gempa di database. Gunakan --simulate{RESET}")
                return
        else:
            earthquake = pending[0]
            eq_id = earthquake["id"]

    # ── Display Earthquake Data ────────────────────────────────
    _header("📍 EARTHQUAKE DATA (BMKG)", BLUE)
    _print_earthquake(earthquake)

    print(f"\n  {DIM}Starting AI Pipeline in 2 seconds...{RESET}")
    time.sleep(2)

    # ─────────────────────────────────────────────────────────
    #  PIPELINE: Step 1 — Analysis Agent
    # ─────────────────────────────────────────────────────────
    _header("🧠 PIPELINE EXECUTION", MAGENTA)
    _step(1, 3, "Analysis Agent — Generating Situation Report", "RUNNING")
    print(f"  {DIM}AI analyzing earthquake parameters + intelligence data...{RESET}")

    t0 = time.time()
    sitrep = analyst.run(eq_id)
    t1 = time.time()

    if sitrep:
        provider = sitrep.get("generated_by", "?")
        risk = sitrep.get("risk_level", "?")
        risk_colors = {"CRITICAL": RED+BOLD, "HIGH": YELLOW+BOLD, "MEDIUM": YELLOW, "LOW": GREEN}
        rc = risk_colors.get(risk, WHITE)
        _step(1, 3, "Analysis Agent", "DONE")
        print(f"\n  {BOLD}📋 Situation Report:{RESET} [{DIM}generated by: {provider}{RESET}] ({t1-t0:.1f}s)")
        _divider("·", 63, DIM)
        print(f"  {BOLD}Risk Level  :{RESET} {rc}{risk}{RESET}")
        print(f"  {BOLD}Summary     :{RESET} {sitrep.get('summary', '')[:150]}...")
        print(f"  {BOLD}Affected    :{RESET} {sitrep.get('affected_areas', '—')}")
    else:
        _step(1, 3, "Analysis Agent", "FAILED")
        print(f"  {RED}Analysis gagal. Cek log untuk detail.{RESET}")
        return

    time.sleep(1)

    # ─────────────────────────────────────────────────────────
    #  PIPELINE: Step 2 — Communication Agent
    # ─────────────────────────────────────────────────────────
    print()
    _step(2, 3, "Communication Agent — Generating 4-Language Alert", "RUNNING")
    print(f"  {DIM}AI drafting alerts in Indonesian, English, Technical, Minang...{RESET}")

    t0 = time.time()
    drafts = comm.run(eq_id)
    t1 = time.time()

    if drafts:
        _step(2, 3, "Communication Agent", "DONE")
        print(f"\n  {BOLD}💬 Multi-Language Alert Output:{RESET} ({t1-t0:.1f}s)")
        _print_multilang_output(drafts)
    else:
        _step(2, 3, "Communication Agent", "FAILED")
        print(f"  {YELLOW}⚠ Draft generation failed — using fallback{RESET}")

    time.sleep(1)

    # ─────────────────────────────────────────────────────────
    #  PIPELINE: Step 3 — Coordination Agent
    # ─────────────────────────────────────────────────────────
    print()
    _step(3, 3, "Coordination Agent — Generating Field Response Plan", "RUNNING")
    print(f"  {DIM}AI mapping resources and prioritizing field actions...{RESET}")

    t0 = time.time()
    plan = coord.run(eq_id)
    t1 = time.time()

    if plan:
        _step(3, 3, "Coordination Agent", "DONE")
        actions = plan.get("action_priorities", [])
        print(f"\n  {BOLD}📌 Field Coordination Plan:{RESET} ({t1-t0:.1f}s)")
        _divider("·", 63, DIM)
        print(f"  {BOLD}Timeline  :{RESET} {plan.get('estimated_timeline', '—')}")
        print(f"  {BOLD}Resources :{RESET} {plan.get('resource_mapping', '')[:100]}...")
        if actions:
            print(f"\n  {BOLD}Priority Actions:{RESET}")
            p_colors = {"P1": RED, "P2": YELLOW, "P3": CYAN}
            for a in actions:
                p = a.get("priority", "?")
                pc = p_colors.get(p, WHITE)
                print(f"    {pc}{BOLD}[{p}]{RESET} {a.get('action', '?')} "
                      f"{DIM}(+{a.get('timeline_hours', '?')}h){RESET}")
                print(f"         {DIM}{a.get('description', '')[:80]}...{RESET}")
    else:
        _step(3, 3, "Coordination Agent", "FAILED")

    # ─────────────────────────────────────────────────────────
    #  Summary
    # ─────────────────────────────────────────────────────────
    _header("✅ PIPELINE COMPLETE", GREEN)
    final_status = llm.get_status()
    _print_provider_status(final_status)
    print(f"  {GREEN}{BOLD}CEPAT AI Orchestrator berhasil memproses gempa ID={eq_id}{RESET}")
    print(f"  {DIM}• {len(drafts)} alert drafts generated in 4 languages{RESET}")
    print(f"  {DIM}• Situation Report: Risk={sitrep.get('risk_level','?')}{RESET}")
    print(f"  {DIM}• Coordination plan: {len(plan.get('action_priorities',[]) if plan else [])} priority actions{RESET}")
    print(f"\n  {DIM}Provider used: {CYAN}{final_status.get('last_provider','?').upper()}{RESET}\n")
    _divider("═", 65, CYAN)


# ─────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CEPAT Expo Demo Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python demo_expo.py              # Demo dengan data gempa live dari BMKG
  python demo_expo.py --simulate   # Demo dengan skenario gempa hardcoded
  python demo_expo.py --status     # Cek status Groq & Ollama
        """
    )
    parser.add_argument(
        "--simulate", action="store_true",
        help="Jalankan demo dengan skenario gempa hardcoded (tidak butuh internet)"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Cek status semua LLM provider"
    )

    args = parser.parse_args()

    try:
        if args.status:
            cmd_status()
        else:
            run_demo(simulate=args.simulate)
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Demo dihentikan.{RESET}\n")
    except Exception as e:
        print(f"\n  {RED}{BOLD}ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
