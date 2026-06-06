"""
demo_expo.py -- CEPAT Expo Demo Script
Script khusus untuk demonstrasi di expo/lomba internasional.

Cara pakai:
    python demo_expo.py --simulate        # RECOMMENDED: skenario M6.5 Mentawai hardcoded
    python demo_expo.py --simulate --fast # Tercepat: ~15-30 detik
    python demo_expo.py --status          # Cek Groq & Ollama sebelum demo
    python demo_expo.py                   # Live data BMKG
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import sys
import os
import time
import logging
import argparse
import sqlite3 as _sqlite3
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────────────────────
#  ANSI Colors
# ─────────────────────────────────────────────────────────────
RESET   = "\033[0m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RED     = "\033[91m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
BLUE    = "\033[94m"
MAGENTA = "\033[95m"
CYAN    = "\033[96m"
WHITE   = "\033[97m"

logging.basicConfig(level=logging.WARNING,
                    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s")

VERSION = "v2.2-expo"

# ─────────────────────────────────────────────────────────────
#  Demo Scenario (M6.5 Mentawai — Hardcoded untuk expo)
# ─────────────────────────────────────────────────────────────
DEMO_EVENT_ID = "DEMO_MENTAWAI_M65_EXPO"
DEMO_EARTHQUAKE = {
    "event_id":         DEMO_EVENT_ID,
    "magnitude":        6.5,
    "location_desc":    "87 km BaratDaya KEPULAUAN MENTAWAI-SUMBAR",
    "depth_km":         12.0,
    "latitude":         -2.45,
    "longitude":        99.32,
    "timestamp":        datetime.now().isoformat(),
    "tsunami_potential":"Gempa ini BERPOTENSI TSUNAMI",
    "felt_area":        "Padang, Pariaman, Painan, Sijunjung",
    "pipeline_status":  "PENDING",
    "source":           "DEMO",
}


# ─────────────────────────────────────────────────────────────
#  Print Helpers
# ─────────────────────────────────────────────────────────────

def _divider(char="-", width=68, color=DIM):
    print(f"{color}{char * width}{RESET}")


def _header(text, color=CYAN, width=68):
    pad = (width - len(text) - 2) // 2
    print(f"\n{color}{BOLD}{'=' * width}{RESET}")
    print(f"{color}{BOLD}{'=' * pad} {text} {'=' * (width - pad - len(text) - 2)}{RESET}")
    print(f"{color}{BOLD}{'=' * width}{RESET}\n")


def _step(num, total, name, status="RUNNING"):
    colors = {"RUNNING": YELLOW, "DONE": GREEN, "FAILED": RED, "SKIP": DIM}
    icons  = {"RUNNING": ">", "DONE": "OK", "FAILED": "XX", "SKIP": "--"}
    c = colors.get(status, WHITE)
    i = icons.get(status, "?")
    print(f"  {c}{BOLD}[{i}] Step {num}/{total}: {name}{RESET}")


def _wrap(text, indent="    ", width=70):
    words, line = text.split(), indent
    for w in words:
        if len(line) + len(w) + 1 > width:
            print(f"{WHITE}{line}{RESET}")
            line = indent + w + " "
        else:
            line += w + " "
    if line.strip():
        print(f"{WHITE}{line}{RESET}")


def _print_provider_status(status, show_counts=False):
    groq_ok   = status.get("groq_available")
    ollama_ok = status.get("ollama_available")
    mode      = status.get("mode", "fallback")
    last      = status.get("last_provider", "none")

    mode_labels = {
        "hybrid":     f"{GREEN}HYBRID (Groq Primary -> Ollama Auto-Failover){RESET}",
        "groq_only":  f"{CYAN}GROQ CLOUD ONLY{RESET}",
        "ollama_only":f"{CYAN}OLLAMA LOCAL ONLY{RESET}",
        "fallback":   f"{YELLOW}RULE-BASED FALLBACK{RESET}",
    }
    groq_icon   = f"{GREEN}[OK] READY{RESET}" if groq_ok   else f"{RED}[X] Not Available{RESET}"
    ollama_icon = f"{GREEN}[OK] READY{RESET}" if ollama_ok else f"{YELLOW}[!] Not Running{RESET}"

    print(f"\n  {BOLD}+------------------------------------------------------+{RESET}")
    print(f"  {BOLD}|          CEPAT AI Provider Status                    |{RESET}")
    print(f"  {BOLD}+------------------------------------------------------+{RESET}")
    print(f"  {BOLD}|{RESET}  [Cloud] Groq   [{status.get('groq_model','N/A'):<22}]  {groq_icon}")
    print(f"  {BOLD}|{RESET}  [Local] Ollama [{status.get('ollama_model','N/A'):<22}]  {ollama_icon}")
    print(f"  {BOLD}|{RESET}  [Mode ] {mode_labels.get(mode, mode)}")
    if show_counts:
        gc = status.get("groq_call_count", 0)
        oc = status.get("ollama_call_count", 0)
        print(f"  {BOLD}|{RESET}  [Calls] Groq={gc}  Ollama={oc}")
    if last != "none":
        lc = GREEN if last == "groq" else CYAN if last == "ollama" else YELLOW
        print(f"  {BOLD}|{RESET}  [Used ] {lc}{BOLD}{last.upper()}{RESET}")
    print(f"  {BOLD}+------------------------------------------------------+{RESET}\n")


def _print_earthquake(eq):
    mag = eq.get("magnitude", "?")
    ts  = eq.get("timestamp", "?")
    try:
        ts = datetime.fromisoformat(str(ts)).strftime("%d %b %Y %H:%M WIB")
    except Exception:
        pass
    tsunami     = eq.get("tsunami_potential", "")
    is_tsunami  = "berpotensi" in tsunami.lower() and "tidak" not in tsunami.lower()
    tsunami_txt = (f"{RED}{BOLD}[!!] TSUNAMI POTENTIAL — EVACUATE COASTAL AREAS{RESET}"
                   if is_tsunami else f"{GREEN}[OK] No tsunami threat detected{RESET}")
    mag_val = float(mag) if str(mag).replace(".","").isdigit() else 0
    mc = RED+BOLD if mag_val >= 7 else YELLOW+BOLD

    _divider(".", 66, DIM)
    print(f"  {BOLD}Magnitude  :{RESET} {mc}M{mag} SR{RESET}")
    print(f"  {BOLD}Location   :{RESET} {WHITE}{BOLD}{eq.get('location_desc','?')}{RESET}")
    print(f"  {BOLD}Depth      :{RESET} {eq.get('depth_km','?')} km")
    print(f"  {BOLD}Time (WIB) :{RESET} {ts}")
    print(f"  {BOLD}Felt in    :{RESET} {eq.get('felt_area','-')}")
    print(f"  {BOLD}Coordinates:{RESET} {eq.get('latitude','?')}, {eq.get('longitude','?')}")
    print(f"  {BOLD}Tsunami    :{RESET} {tsunami_txt}")
    _divider(".", 66, DIM)


def _print_multilang(drafts):
    draft_map = {d["draft_type"]: d["content"] for d in drafts}
    for key, flag, label in [
        ("public_id",     "[ID]", "BAHASA INDONESIA (Publik)"),
        ("english",       "[EN]", "ENGLISH (International Alert)"),
        ("technical",     "[TK]", "TECHNICAL REPORT (Formal)"),
        ("public_minang", "[MN]", "BAHASA MINANG (Local Community)"),
    ]:
        content = draft_map.get(key, "")
        if not content:
            continue
        print(f"\n  {flag} {BOLD}{CYAN}{label}{RESET}")
        _divider(".", 66, DIM)
        _wrap(content, "  ", 72)


def _print_timing(elapsed, provider):
    pc = GREEN if provider == "groq" else CYAN if provider == "ollama" else YELLOW
    pl = provider.upper() if provider != "none" else "RULE-BASED"
    print(f"  {DIM}  Time: {elapsed:.1f}s  |  Provider: {pc}{pl}{RESET}")


# ─────────────────────────────────────────────────────────────
#  DB Helper: bersihkan demo data agar fresh setiap run
# ─────────────────────────────────────────────────────────────

def _clean_demo_data(db_path, event_id_str):
    conn = _sqlite3.connect(db_path)
    row = conn.execute("SELECT id FROM earthquakes WHERE event_id=?", (event_id_str,)).fetchone()
    if row:
        old_id = row[0]
        for tbl in ("situation_reports", "communication_drafts",
                    "coordination_plans", "intelligence_reports"):
            conn.execute(f"DELETE FROM {tbl} WHERE earthquake_id=?", (old_id,))
        conn.execute("DELETE FROM earthquakes WHERE id=?", (old_id,))
        conn.commit()
    conn.close()


# ─────────────────────────────────────────────────────────────
#  Mode: Status Check
# ─────────────────────────────────────────────────────────────

def cmd_status():
    _header("CEPAT — LLM Provider Status Check", CYAN)
    print(f"  {BOLD}Checking all AI providers...{RESET}\n")

    from utils.llm_client import LLMClient
    client = LLMClient()
    status = client.get_status()
    _print_provider_status(status)

    if status.get("groq_available"):
        print(f"  {BOLD}Testing Groq...{RESET}")
        r = client._generate_groq("Say exactly: 'CEPAT system online. Groq ready.' Nothing else.", max_tokens=30)
        if r:
            print(f"  {GREEN}[OK] Groq WORKING:{RESET} {r[:100]}")
        else:
            print(f"  {RED}[X] Groq FAILED — check API key & internet{RESET}")
    else:
        print(f"  {YELLOW}[!] Groq skipped — no valid GROQ_API_KEY in .env{RESET}")

    if status.get("ollama_available"):
        print(f"\n  {BOLD}Testing Ollama...{RESET}")
        r2 = client._generate_ollama("Say exactly: 'Ollama ready.' Nothing else.", max_tokens=10)
        if r2:
            print(f"  {GREEN}[OK] Ollama WORKING:{RESET} {r2[:100]}")
        else:
            print(f"  {RED}[X] Ollama FAILED — run: ollama serve{RESET}")
    else:
        print(f"\n  {YELLOW}[!] Ollama not running — for offline backup:{RESET}")
        print(f"  {DIM}      1. Download: https://ollama.com/download{RESET}")
        print(f"  {DIM}      2. Run: ollama pull {status.get('ollama_model','qwen2.5:7b')}{RESET}")
        print(f"  {DIM}      3. Run: ollama serve{RESET}")

    _divider()
    print(f"\n  {GREEN}{BOLD}Status check complete.{RESET}\n")


# ─────────────────────────────────────────────────────────────
#  Mode: Full Pipeline Demo
# ─────────────────────────────────────────────────────────────

def run_demo(simulate=False, fast_mode=False):
    mode_label = "FAST MODE" if fast_mode else "FULL DEMO"
    _header(f"CEPAT AI Orchestrator — {mode_label}", CYAN)
    print(f"  {DIM}CEPAT: Centralized Emergency Prediction and Alert Technology{RESET}")
    print(f"  {DIM}AI-Powered Earthquake Response Orchestrator — Expo Demo {VERSION}{RESET}")
    if fast_mode:
        print(f"\n  {YELLOW}{BOLD}[FAST] FAST MODE: Skip Intelligence LLM for speed (~30s){RESET}")

    # ── Init DB & Agents ──────────────────────────────────────
    print(f"\n  {BOLD}[*] Initializing AI Agents...{RESET}")
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

    # ── Get Earthquake ────────────────────────────────────────
    earthquake = None
    eq_id      = None

    if simulate:
        print(f"  {MAGENTA}{BOLD}[SIM] SIMULATION MODE — Hardcoded M6.5 Mentawai Scenario{RESET}")
        print(f"  {DIM}      (Stable expo scenario, no live data needed){RESET}\n")

        earthquake = DEMO_EARTHQUAKE.copy()
        earthquake["timestamp"] = datetime.now().isoformat()  # Timestamp terkini

        # Bersihkan data lama agar LLM generate fresh setiap demo
        _clean_demo_data(db.db_path, DEMO_EVENT_ID)
        db.insert_earthquake(earthquake)

        # Ambil integer ID
        _c = _sqlite3.connect(db.db_path)
        _r = _c.execute("SELECT id FROM earthquakes WHERE event_id=?", (DEMO_EVENT_ID,)).fetchone()
        _c.close()

        if not _r:
            print(f"  {RED}[ERROR] Gagal menyimpan skenario demo ke database.{RESET}")
            return

        eq_id = _r[0]
        earthquake["id"] = eq_id
        print(f"  {DIM}  Demo data ready (DB ID: {eq_id}){RESET}\n")

    else:
        print(f"  {BOLD}[*] Fetching live earthquake data from BMKG...{RESET}")
        from agents.monitoring_agent import MonitoringAgent
        monitor = MonitoringAgent(db_handler=db)
        try:
            monitor.poll_once()
        except Exception as e:
            print(f"  {YELLOW}[!] BMKG poll failed: {e}{RESET}")

        pending = db.get_pending_earthquakes(min_magnitude=5.0)
        if not pending:
            _c2 = _sqlite3.connect(db.db_path)
            _c2.row_factory = _sqlite3.Row
            _r2 = _c2.execute("SELECT * FROM earthquakes ORDER BY id DESC LIMIT 1").fetchone()
            _c2.close()
            if _r2:
                earthquake = dict(_r2)
                eq_id = earthquake["id"]
                db.update_pipeline_status(eq_id, "PENDING")
            else:
                print(f"  {RED}[ERROR] No earthquake data. Use --simulate.{RESET}")
                return
        else:
            earthquake = pending[0]
            eq_id = earthquake["id"]

    # ── Show Earthquake ───────────────────────────────────────
    _header("EARTHQUAKE EVENT — BMKG DATA", BLUE)
    _print_earthquake(earthquake)

    print(f"\n  {DIM}Starting AI Pipeline in 2 seconds...{RESET}")
    time.sleep(2)

    total_steps = 3
    _header("AI PIPELINE EXECUTION", MAGENTA)

    # ── Step 1: Intelligence Agent ────────────────────────────
    if fast_mode:
        _step(1, total_steps, "Intelligence Agent", "SKIP")
        print(f"  {DIM}   (Skipped in fast mode — use full mode for complete demo){RESET}")
    else:
        _step(1, total_steps, "Intelligence Agent — News Collection & Verification", "RUNNING")
        print(f"  {DIM}   Scanning: ANTARA, Detik, Tribun, Google News RSS...{RESET}")
        print(f"  {DIM}   AI classifying credibility: VALID / HOAX / UNVERIFIED...{RESET}")

        t0 = time.time()
        from agents.intelligence_agent import IntelligenceAgent
        intel_agent   = IntelligenceAgent(db_handler=db)
        intel_reports = intel_agent.run(earthquake)
        t1 = time.time()

        valid_c = sum(1 for r in intel_reports if r.get("credibility_status") == "VALID")
        hoax_c  = sum(1 for r in intel_reports if r.get("credibility_status") == "HOAX")

        _step(1, total_steps, "Intelligence Agent", "DONE")
        print(f"\n  {BOLD}Intelligence Collection Results:{RESET}")
        _divider(".", 66, DIM)
        print(f"  {BOLD}Articles Found :{RESET} {len(intel_reports)} relevant")
        print(f"  {BOLD}Verified VALID :{RESET} {GREEN}{valid_c}{RESET}")
        print(f"  {BOLD}Flagged HOAX   :{RESET} {RED}{hoax_c}{RESET}")
        _print_timing(t1 - t0, llm.last_provider)

    time.sleep(1)

    # ── Step 2: Analysis Agent ────────────────────────────────
    print()
    _step(2, total_steps, "Analysis Agent — Situation Report Generation", "RUNNING")
    print(f"  {DIM}   Synthesizing earthquake data + intelligence reports...{RESET}")

    t0 = time.time()
    sitrep = analyst.run(eq_id)
    t1 = time.time()

    if sitrep:
        risk = sitrep.get("risk_level", "?")
        # Ambil provider yang dipakai dari field generated_by
        gen_by = sitrep.get("generated_by", "rule-based")
        sitrep_provider = "groq" if "groq" in str(gen_by).lower() else "ollama" if "ollama" in str(gen_by).lower() else "none"
        rc = {"CRITICAL": RED+BOLD, "HIGH": YELLOW+BOLD, "MEDIUM": YELLOW, "LOW": GREEN}.get(risk, WHITE)
        _step(2, total_steps, "Analysis Agent", "DONE")
        print(f"\n  {BOLD}Situation Report:{RESET}")
        _divider(".", 66, DIM)
        print(f"  {BOLD}Risk Level     :{RESET} {rc}{risk}{RESET}")
        print(f"  {BOLD}Summary        :{RESET}")
        _wrap(sitrep.get("summary", ""), "    ")
        print(f"  {BOLD}Affected Areas :{RESET} {sitrep.get('affected_areas', '-')}")
        recs = sitrep.get("recommendations", [])
        if isinstance(recs, str):
            import json as _j
            try: recs = _j.loads(recs)
            except: recs = [recs]
        if recs:
            print(f"  {BOLD}Key Actions    :{RESET}")
            for i, r in enumerate(recs[:3], 1):
                print(f"    {GREEN}{i}.{RESET} {r[:90]}")
        _print_timing(t1 - t0, sitrep_provider)
    else:
        _step(2, total_steps, "Analysis Agent", "FAILED")
        print(f"  {RED}[ERROR] Analysis failed. Check API key in .env{RESET}")
        return

    time.sleep(1)

    # ── Step 3: Communication Agent ───────────────────────────
    print()
    _step(3, total_steps, "Communication Agent — Multi-Language Alert", "RUNNING")
    print(f"  {DIM}   Drafting: Indonesian, English, Technical, Minang...{RESET}")

    t0 = time.time()
    drafts = comm.run(eq_id)
    t1 = time.time()

    if drafts:
        _step(3, total_steps, "Communication Agent", "DONE")
        # Cek apakah drafts dihasilkan oleh LLM atau fallback
        comm_provider = "none"
        if drafts and any("groq" in str(d.get("generated_by", "")).lower() for d in drafts):
            comm_provider = "groq"
        elif drafts and any("ollama" in str(d.get("generated_by", "")).lower() for d in drafts):
            comm_provider = "ollama"
        elif sitrep_provider != "none":  # Communication berhasil (LLM atau fallback dari sitrep LLM)
            comm_provider = sitrep_provider
        print(f"\n  {BOLD}Multi-Language Alert Output:{RESET}")
        _print_multilang(drafts)
        _print_timing(t1 - t0, comm_provider)
    else:
        _step(3, total_steps, "Communication Agent", "FAILED")

    time.sleep(1)

    # ── Bonus: Coordination Agent ─────────────────────────────
    print()
    print(f"  {CYAN}{BOLD}[+] Coordination Agent — Field Response Plan{RESET}")
    print(f"  {DIM}   Mapping resources & prioritizing field actions...{RESET}")

    t0 = time.time()
    plan = coord.run(eq_id)
    t1 = time.time()

    if plan:
        actions = plan.get("action_priorities", [])
        print(f"\n  {BOLD}Field Coordination Plan:{RESET}")
        _divider(".", 66, DIM)
        print(f"  {BOLD}Timeline  :{RESET} {plan.get('estimated_timeline', '-')}")
        if actions:
            print(f"  {BOLD}Priority Actions:{RESET}")
            for a in actions[:5]:
                p  = a.get("priority", "?")
                pc = {"P1": RED, "P2": YELLOW, "P3": CYAN}.get(p, WHITE)
                print(f"    {pc}{BOLD}[{p}]{RESET} {a.get('action','?')} {DIM}(+{a.get('timeline_hours','?')}h){RESET}")
                desc = a.get("description", "")[:85]
                if desc:
                    print(f"         {DIM}{desc}...{RESET}")
        coord_provider = plan.get("generated_by", "none").split(":")[-1]
        _print_timing(t1 - t0, coord_provider)
    else:
        print(f"  {YELLOW}[!] Coordination plan using rule-based fallback{RESET}")

    # ── Final Summary ─────────────────────────────────────────
    _header("PIPELINE COMPLETE — CEPAT DEMO", GREEN)
    final_status = llm.get_status()
    _print_provider_status(final_status, show_counts=True)

    print(f"  {GREEN}{BOLD}[OK] CEPAT successfully processed Earthquake ID={eq_id}{RESET}")
    print(f"  {BOLD}Results Summary:{RESET}")
    print(f"    {GREEN}>{RESET} Situation Report  : Risk Level = {sitrep.get('risk_level','?')}")
    print(f"    {GREEN}>{RESET} Alerts Generated  : {len(drafts)} drafts in 4 languages")
    print(f"    {GREEN}>{RESET} Coordination Plan : {len(plan.get('action_priorities',[]) if plan else [])} priority actions")
    print(f"\n  {DIM}CEPAT — Centralized Emergency Prediction and Alert Technology{RESET}")
    print(f"  {DIM}AI: Groq ({final_status.get('groq_model','?')}) + Ollama ({final_status.get('ollama_model','?')}){RESET}\n")
    _divider("=", 68, CYAN)


# ─────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="CEPAT Expo Demo Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python demo_expo.py --simulate         # Best for expo: stable M6.5 Mentawai scenario
  python demo_expo.py --simulate --fast  # Fastest: ~15-30 seconds
  python demo_expo.py --status           # Check Groq & Ollama before demo
  python demo_expo.py                    # Live BMKG data
        """
    )
    parser.add_argument("--simulate", action="store_true",
                        help="Use hardcoded M6.5 scenario (recommended for expo)")
    parser.add_argument("--fast", action="store_true",
                        help="Fast mode: skip Intelligence LLM (~15-30s)")
    parser.add_argument("--status", action="store_true",
                        help="Check all LLM providers (Groq & Ollama)")

    args = parser.parse_args()

    try:
        if args.status:
            cmd_status()
        else:
            run_demo(simulate=args.simulate, fast_mode=args.fast)
    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Demo stopped by user.{RESET}\n")
    except Exception as e:
        print(f"\n  {RED}{BOLD}ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
