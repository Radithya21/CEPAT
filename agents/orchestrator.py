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

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db = db_handler or DatabaseHandler()

        # Inisialisasi semua agent dengan shared DB handler
        self.monitoring_agent    = MonitoringAgent(db_handler=self.db)
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

        # Step 1: Update status → PROCESSING
        self.db.update_pipeline_status(eq_id, "PROCESSING")

        try:
            # Step 2: Intelligence Agent
            logger.info(f"[Step 2/5] Intelligence Agent untuk gempa {eq_id}…")
            intel_reports = self.intelligence_agent.run(earthquake)
            result["intel"] = len(intel_reports)
            self._stats["total_intel_reports"] += len(intel_reports)

            # Step 3: Analysis Agent
            logger.info(f"[Step 3/5] Analysis Agent untuk gempa {eq_id}…")
            sitrep = self.analysis_agent.run(eq_id)
            result["sitrep"] = sitrep

            if sitrep:
                self._stats["total_sitreps"] += 1
                if sitrep.get("generated_by") == "llm":
                    self._stats["total_sitreps_llm"] += 1
                else:
                    self._stats["total_sitreps_fallback"] += 1

                # Step 4: Communication Agent (hanya jika sitrep berhasil)
                logger.info(f"[Step 4/5] Communication Agent untuk gempa {eq_id}…")
                comm_drafts = self.communication_agent.run(eq_id)
                result["comm_drafts"] = len(comm_drafts)
                self._stats["total_comm_drafts"] += len(comm_drafts)

                # Step 5: Coordination Agent
                logger.info(f"[Step 5/5] Coordination Agent untuk gempa {eq_id}…")
                coord_plan = self.coordination_agent.run(eq_id)
                result["coord_plan"] = coord_plan
                if coord_plan:
                    self._stats["total_coord_plans"] += 1

            # Done
            self.db.update_pipeline_status(eq_id, "DONE")
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

            try:
                # Step 1: Monitoring Agent
                logger.info("[Step 1/3] Monitoring Agent — polling BMKG…")
                self.monitoring_agent.poll_once()

                # Step 2 & 3: Process pending events (Intelligence + Analysis)
                logger.info("[Step 2-3/3] Processing pending M≥5 events…")
                self.process_pending_events()

                self.last_error = None

            except Exception as exc:
                self.last_error = str(exc)
                logger.error(f"Error di siklus #{self.cycle_count}: {exc}")

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
