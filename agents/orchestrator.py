"""
orchestrator.py — CEPAT Orchestrator (Fase 2)
Mengkoordinasikan pipeline: Monitoring → Intelligence → Analysis.
Berjalan sebagai background thread, menggantikan monitoring_agent.start()
yang dipakai di Fase 1.
"""

import sys
import os
import time
import logging
import threading
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import POLL_INTERVAL_SECONDS, PIPELINE_MIN_MAGNITUDE
from database.db_handler import DatabaseHandler
from agents.monitoring_agent import MonitoringAgent
from agents.intelligence_agent import IntelligenceAgent
from agents.analysis_agent import AnalysisAgent
from agents.communication_agent import CommunicationAgent
from agents.coordination_agent import CoordinationAgent

logger = logging.getLogger("Orchestrator")


class Orchestrator:
    """
    Pipeline coordinator untuk sistem CEPAT.

    Urutan eksekusi per siklus:
        1. MonitoringAgent  → Poll BMKG, simpan gempa baru ke DB
        2. IntelligenceAgent → Untuk setiap gempa M≥threshold baru,
                               kumpulkan berita + klasifikasi hoax
        3. AnalysisAgent    → Generate Situation Report per gempa

    Cara pakai:
        orc = Orchestrator(db)
        orc.start()           # jalankan di background thread
        orc.stop()            # hentikan
        orc.get_status()      # info status untuk API
    """

    def __init__(self, db_handler: DatabaseHandler = None, on_event = None):
        self.db = db_handler or DatabaseHandler()
        self.on_event = on_event

        # Inisialisasi semua agent dengan shared DB handler
        self.monitoring_agent    = MonitoringAgent(db_handler=self.db, on_event=self.on_event)
        self.intelligence_agent  = IntelligenceAgent(db_handler=self.db)
        self.analysis_agent      = AnalysisAgent(db_handler=self.db)
        self.communication_agent = CommunicationAgent(db_handler=self.db)
        self.coordination_agent  = CoordinationAgent(db_handler=self.db)

        self.is_running    = False
        self._thread: threading.Thread | None = None
        self.cycle_count   = 0
        self.last_cycle_time: datetime | None = None
        self.last_error: str | None = None

        # Stats pipeline
        self._stats = {
            "total_intel_reports":    0,
            "total_sitreps":          0,
            "total_sitreps_llm":      0,
            "total_sitreps_fallback": 0,
            "total_comm_drafts":      0,
            "total_coord_plans":      0,
        }

        # Live activity logs
        self.activity_logs = [
            {
                "ts": datetime.now().isoformat(),
                "ag": "Orchestrator",
                "st": "ok",
                "d": "Orchestrator diinisialisasi dan siap menerima sinyal monitoring."
            }
        ]

    def log_activity(self, agent: str, status: str, description: str):
        log_entry = {
            "ts": datetime.now().isoformat(),
            "ag": agent,
            "st": status,  # "proc" | "ok" | "wait"
            "d": description
        }
        self.activity_logs.insert(0, log_entry)
        if len(self.activity_logs) > 50:
            self.activity_logs.pop()

        if self.on_event:
            try:
                self.on_event("agent_activity", log_entry)
            except Exception as e:
                logger.error(f"Gagal emit agent_activity: {e}")


    # ─────────────────────────────────────────────────────────
    #  Single Pipeline Run
    # ─────────────────────────────────────────────────────────

    def run_pipeline_for_earthquake(self, earthquake: dict) -> dict:
        """
        Jalankan full pipeline (Intelligence → Analysis) untuk satu gempa.
        Return ringkasan hasil.
        """
        eq_id  = earthquake["id"]
        eq_mag = earthquake.get("magnitude", 0)
        result = {
            "earthquake_id": eq_id,
            "magnitude":     eq_mag,
            "intel":         0,
            "sitrep":        None,
            "comm_drafts":   0,
            "coord_plan":    None,
        }

        logger.info(f"━━━ Pipeline: Gempa ID={eq_id} M{eq_mag} ━━━")
        self.log_activity("Orchestrator", "proc", f"Memulai koordinasi pipeline untuk Gempa ID {eq_id} (M{eq_mag})")

        # Step 1: Update status → PROCESSING
        self.db.update_pipeline_status(eq_id, "PROCESSING")

        try:
            # Step 2: Intelligence Agent
            logger.info(f"[Step 2/5] Intelligence Agent untuk gempa {eq_id}…")
            self.log_activity("Intelligence Agent", "proc", f"Mencari berita lokal dan mendeteksi hoaks untuk Gempa ID {eq_id}...")
            intel_reports = self.intelligence_agent.run(earthquake)
            result["intel"] = len(intel_reports)
            self._stats["total_intel_reports"] += len(intel_reports)
            self.log_activity("Intelligence Agent", "ok", f"Selesai. Menemukan {len(intel_reports)} laporan berita.")

            # Step 3: Analysis Agent
            logger.info(f"[Step 3/5] Analysis Agent untuk gempa {eq_id}…")
            self.log_activity("Analysis Agent", "proc", f"Membuat Situation Report dengan LLM untuk Gempa ID {eq_id}...")
            sitrep = self.analysis_agent.run(eq_id)
            result["sitrep"] = sitrep

            if sitrep:
                self._stats["total_sitreps"] += 1
                if sitrep.get("generated_by") == "llm":
                    self._stats["total_sitreps_llm"] += 1
                else:
                    self._stats["total_sitreps_fallback"] += 1
                self.log_activity("Analysis Agent", "ok", f"Situation Report selesai dibuat. Risk level: {sitrep.get('risk_level', 'MEDIUM')}")

                # Step 4: Communication Agent (hanya jika sitrep berhasil)
                logger.info(f"[Step 4/5] Communication Agent untuk gempa {eq_id}…")
                self.log_activity("Communication Agent", "proc", f"Menyusun draf peringatan multibahasa untuk Gempa ID {eq_id}...")
                comm_drafts = self.communication_agent.run(eq_id)
                result["comm_drafts"] = len(comm_drafts)
                self._stats["total_comm_drafts"] += len(comm_drafts)
                self.log_activity("Communication Agent", "ok", f"Selesai menyusun {len(comm_drafts)} draf peringatan.")

                if self.on_event and len(comm_drafts) > 0:
                    try:
                        self.on_event("draft_pending", {
                            "earthquake_id": eq_id,
                            "drafts_count": len(comm_drafts)
                        })
                    except Exception as e:
                        logger.error(f"Gagal emit draft_pending: {e}")

                # Step 5: Coordination Agent
                logger.info(f"[Step 5/5] Coordination Agent untuk gempa {eq_id}…")
                self.log_activity("Coordination Agent", "proc", f"Menyusun rencana koordinasi dan logistik untuk Gempa ID {eq_id}...")
                coord_plan = self.coordination_agent.run(eq_id)
                result["coord_plan"] = coord_plan
                if coord_plan:
                    self._stats["total_coord_plans"] += 1
                self.log_activity("Coordination Agent", "ok", "Rencana koordinasi dan alokasi logistik selesai dibuat.")

                # ── Auto-Approve untuk LOW / MEDIUM risk ─────────────────────────────────────
                # Hanya gempa dengan risk level HIGH / CRITICAL yang wajib melalui verifikasi manual (Human-in-the-Loop)
                risk_level = sitrep.get("risk_level", "MEDIUM")
                if risk_level in {"LOW", "MEDIUM"}:
                    logger.info(f"[Auto-Approve] Risk={risk_level} → auto-approving drafts & plan untuk gempa {eq_id}…")
                    officer = "AutoApprove-System"
                    drafts_in_db = self.db.get_communication_drafts(eq_id)
                    for d in drafts_in_db:
                        self.db.approve_communication_draft(d["id"], officer)
                        self.db.insert_audit_log({
                            "action_type":  "APPROVE",
                            "item_table":   "communication_drafts",
                            "item_id":      d["id"],
                            "decision":     "APPROVED",
                            "officer_name": officer,
                            "notes":        f"Auto-approved: risk level {risk_level}",
                        })
                    if coord_plan and coord_plan.get("id"):
                        self.db.approve_coordination_plan(coord_plan["id"], officer)
                        self.db.insert_audit_log({
                            "action_type":  "APPROVE",
                            "item_table":   "coordination_plans",
                            "item_id":      coord_plan["id"],
                            "decision":     "APPROVED",
                            "officer_name": officer,
                            "notes":        f"Auto-approved: risk level {risk_level}",
                        })
                    logger.info(f"[Auto-Approve] Selesai — {len(drafts_in_db)} draft + plan di-approve otomatis.")
                    self.log_activity("Orchestrator", "ok", f"Auto-Approve selesai: Risk {risk_level} disetujui otomatis.")
                else:
                    reason = f"Risk {risk_level} dideteksi"
                    logger.info(f"[Manual-Approval] {reason} → draft & plan menunggu persetujuan operator.")
                    self.log_activity("Orchestrator", "wait", f"{reason}. Menunggu persetujuan manual.")
            else:
                self.log_activity("Analysis Agent", "wait", "Gagal membuat Situation Report.")

            # Done
            self.db.update_pipeline_status(eq_id, "DONE")
            self.log_activity("Orchestrator", "ok", f"Pipeline selesai untuk Gempa ID {eq_id}.")

            if self.on_event:
                try:
                    self.on_event("pipeline_done", {
                        "earthquake_id": eq_id,
                        "magnitude": eq_mag,
                        "location": earthquake.get("location_desc", "—"),
                        "timestamp": earthquake.get("timestamp", "—")
                    })
                except Exception as e:
                    logger.error(f"Gagal emit pipeline_done: {e}")
            logger.info(
                f"✔ Pipeline selesai: Gempa {eq_id} | "
                f"{len(intel_reports)} intel | "
                f"Sitrep={sitrep.get('risk_level', 'N/A') if sitrep else 'GAGAL'} | "
                f"{result['comm_drafts']} draf | "
                f"Plan={'OK' if result['coord_plan'] else 'GAGAL'}"
            )

        except Exception as exc:
            self.last_error = str(exc)
            logger.error(f"✘ Pipeline gagal untuk gempa {eq_id}: {exc}")
            self.db.update_pipeline_status(eq_id, "FAILED")
            result["error"] = str(exc)
            self.log_activity("Orchestrator", "wait", f"Gagal memproses pipeline Gempa ID {eq_id}: {exc}")

        return result

    def process_pending_events(self) -> list[dict]:
        """Proses semua gempa M≥threshold yang belum dijalankan pipeline-nya."""
        pending = self.db.get_pending_earthquakes(min_magnitude=PIPELINE_MIN_MAGNITUDE)

        if not pending:
            logger.debug("Tidak ada gempa pending untuk diproses.")
            return []

        logger.info(f"Memproses {len(pending)} gempa pending…")
        results = []
        for eq in pending:
            result = self.run_pipeline_for_earthquake(eq)
            results.append(result)

        return results

    # ─────────────────────────────────────────────────────────
    #  Main Loop
    # ─────────────────────────────────────────────────────────

    def _run_loop(self):
        """Loop utama orchestrator (berjalan di background thread)."""
        logger.info(
            f"🚀 Orchestrator aktif | interval={POLL_INTERVAL_SECONDS}s "
            f"| pipeline_threshold=M≥{PIPELINE_MIN_MAGNITUDE}"
        )

        while self.is_running:
            self.cycle_count += 1
            self.last_cycle_time = datetime.now()
            logger.info(f"\n{'='*55}")
            logger.info(f"  SIKLUS #{self.cycle_count} — {self.last_cycle_time.strftime('%H:%M:%S')}")
            logger.info(f"{'='*55}")
            self.log_activity("Orchestrator", "proc", f"Memulai Siklus #{self.cycle_count} pemantauan...")

            try:
                # Step 1: Monitoring Agent
                logger.info("[Step 1/3] Monitoring Agent — polling BMKG…")
                self.log_activity("Monitoring Agent", "proc", "Menghubungi API BMKG untuk mendeteksi aktivitas gempa bumi terbaru...")
                summary = self.monitoring_agent.poll_once()
                new_eqs = summary.get("new", 0)
                if new_eqs > 0:
                    self.log_activity("Monitoring Agent", "ok", f"Terdeteksi {new_eqs} gempa baru dari BMKG!")
                else:
                    self.log_activity("Monitoring Agent", "ok", "Polling selesai. Tidak ada aktivitas seismik baru terdeteksi.")

                # Step 2 & 3: Process pending events (Intelligence + Analysis)
                logger.info("[Step 2-3/3] Processing pending M≥5 events…")
                self.process_pending_events()

                self.last_error = None
                self.log_activity("Orchestrator", "ok", f"Siklus #{self.cycle_count} selesai. Sistem standby.")

            except Exception as exc:
                self.last_error = str(exc)
                logger.error(f"Error di siklus #{self.cycle_count}: {exc}")
                self.log_activity("Orchestrator", "wait", f"Error pada siklus #{self.cycle_count}: {exc}")

            if self.is_running:
                logger.info(f"Siklus berikutnya dalam {POLL_INTERVAL_SECONDS} detik…")
                for _ in range(POLL_INTERVAL_SECONDS):
                    if not self.is_running:
                        break
                    time.sleep(1)

        logger.info("🔴 Orchestrator dihentikan.")

    # ─────────────────────────────────────────────────────────
    #  Thread Control
    # ─────────────────────────────────────────────────────────

    def start(self):
        """Mulai orchestrator di background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("Orchestrator sudah berjalan.")
            return
        self.is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="Orchestrator",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"Thread '{self._thread.name}' dimulai (daemon=True).")

    def stop(self):
        """Hentikan orchestrator."""
        self.is_running = False
        if self.monitoring_agent:
            self.monitoring_agent.is_running = False
        logger.info("Sinyal stop dikirim ke Orchestrator.")

    # ─────────────────────────────────────────────────────────
    #  Status (untuk API)
    # ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "is_running":           self.is_running,
            "cycle_count":          self.cycle_count,
            "last_cycle_time":      self.last_cycle_time.isoformat() if self.last_cycle_time else None,
            "last_error":           self.last_error,
            "poll_interval_sec":    POLL_INTERVAL_SECONDS,
            "pipeline_threshold":   PIPELINE_MIN_MAGNITUDE,
            "poll_count":           self.monitoring_agent.poll_count,
            "last_poll_time":       self.monitoring_agent.last_poll_time.isoformat()
                                    if self.monitoring_agent.last_poll_time else None,
            **self._stats,
            "approval_stats":       self.db.get_approval_stats(),
        }


# ─────────────────────────────────────────────────────────────
#  Test standalone
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    orc = Orchestrator()
    # Jalankan satu siklus penuh untuk testing
    orc.monitoring_agent.poll_once()
    results = orc.process_pending_events()
    print(f"\nPipeline selesai: {len(results)} gempa diproses")
    for r in results:
        print(f"  Gempa {r['earthquake_id']} M{r['magnitude']}: "
              f"{r['intel']} intel, sitrep={r.get('sitrep', {}).get('risk_level', 'N/A') if r.get('sitrep') else 'GAGAL'}")
