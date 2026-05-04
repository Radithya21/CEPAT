"""
monitoring_agent.py — CEPAT Monitoring Agent
Polling BMKG REST API setiap N menit, parse data gempa,
dan simpan event ke database SQLite.
"""

import requests
import logging
import time
import threading
import sys
import os
from datetime import datetime

# Resolve root path agar import config & database bisa berjalan
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    BMKG_LATEST_URL,
    BMKG_RECENT_URL,
    BMKG_TIMEOUT_SEC,
    POLL_INTERVAL_SECONDS,
    MAGNITUDE_THRESHOLD,
)
from database.db_handler import DatabaseHandler

# ─────────────────────────────────────────────────────────────
#  Logger
# ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("MonitoringAgent")


class MonitoringAgent:
    """
    Agent pemantau gempa BMKG.

    Cara pakai:
        agent = MonitoringAgent()
        agent.start()        # jalankan di background thread (non-blocking)
        agent.poll_once()    # satu siklus polling (untuk testing)
        agent.stop()         # hentikan background thread
    """

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db          = db_handler or DatabaseHandler()
        self.is_running  = False
        self._thread: threading.Thread | None = None
        self.last_poll_time: datetime | None  = None
        self.poll_count  = 0
        self.last_error: str | None = None

    # ─────────────────────────────────────────────────────────
    #  Parsing
    # ─────────────────────────────────────────────────────────

    def _parse_gempa(self, raw: dict) -> dict | None:
        """
        Konversi satu entry gempa dari JSON BMKG ke format internal.
        Return None jika data tidak valid.
        """
        try:
            # Koordinat ada dalam string "lat,lon"
            coords_str = raw.get("Coordinates", "0,0")
            parts = coords_str.split(",")
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())

            magnitude = float(raw.get("Magnitude", 0))

            # Kedalaman: "10 km" → 10.0
            depth_raw = raw.get("Kedalaman", "0 km")
            depth_km  = float(depth_raw.replace(" km", "").strip())

            # Gunakan DateTime ISO sebagai event_id unik
            event_id = raw.get("DateTime", "").strip()
            if not event_id:
                # Fallback: gabung tanggal + jam
                event_id = f"{raw.get('Tanggal','')}_{raw.get('Jam','')}".replace(" ", "_")

            return {
                "event_id":          event_id,
                "magnitude":         magnitude,
                "depth_km":          depth_km,
                "latitude":          lat,
                "longitude":         lon,
                "location_desc":     raw.get("Wilayah", "Unknown"),
                "timestamp":         event_id,
                "felt_area":         raw.get("Dirasakan", ""),
                "tsunami_potential": raw.get("Potensi", ""),
            }
        except Exception as exc:
            logger.warning(f"Gagal parse data gempa: {exc} | raw={raw}")
            return None

    # ─────────────────────────────────────────────────────────
    #  Fetch BMKG
    # ─────────────────────────────────────────────────────────

    def _fetch_recent(self) -> list[dict]:
        """Ambil ~15 gempa terkini dari BMKG."""
        try:
            resp = requests.get(BMKG_RECENT_URL, timeout=BMKG_TIMEOUT_SEC)
            resp.raise_for_status()
            return resp.json().get("Infogempa", {}).get("gempa", [])
        except requests.exceptions.ConnectionError:
            logger.warning("Tidak bisa terhubung ke BMKG API (ConnectionError)")
        except requests.exceptions.Timeout:
            logger.warning("Request ke BMKG API timeout")
        except requests.exceptions.HTTPError as e:
            logger.warning(f"HTTP error dari BMKG: {e}")
        except Exception as e:
            logger.error(f"Error tidak terduga saat fetch recent: {e}")
        return []

    def _fetch_latest(self) -> list[dict]:
        """Ambil gempa paling terakhir (single entry)."""
        try:
            resp = requests.get(BMKG_LATEST_URL, timeout=BMKG_TIMEOUT_SEC)
            resp.raise_for_status()
            gempa = resp.json().get("Infogempa", {}).get("gempa")
            return [gempa] if isinstance(gempa, dict) else []
        except Exception as e:
            logger.error(f"Error tidak terduga saat fetch latest: {e}")
        return []

    # ─────────────────────────────────────────────────────────
    #  Processing
    # ─────────────────────────────────────────────────────────

    def _process(self, raw_list: list[dict]) -> tuple[int, int]:
        """
        Parse & simpan daftar gempa ke DB.
        Return (jumlah_baru, jumlah_M_besar).
        """
        new_count  = 0
        high_count = 0

        for raw in raw_list:
            eq = self._parse_gempa(raw)
            if eq is None:
                continue

            inserted = self.db.insert_earthquake(eq)
            if inserted:
                new_count += 1
                if eq["magnitude"] >= MAGNITUDE_THRESHOLD:
                    high_count += 1
                    logger.warning(
                        f"⚠  ALERT M{eq['magnitude']} — {eq['location_desc']}"
                        f" (kedalaman {eq['depth_km']} km)"
                    )

        return new_count, high_count

    # ─────────────────────────────────────────────────────────
    #  Polling Cycle
    # ─────────────────────────────────────────────────────────

    def poll_once(self) -> dict:
        """
        Satu siklus polling lengkap:
        1. Fetch recent + latest dari BMKG
        2. Parse & simpan ke DB
        3. Return ringkasan hasil
        """
        self.poll_count += 1
        logger.info(f"▶ Poll #{self.poll_count} dimulai ...")

        all_raw: list[dict] = []
        all_raw.extend(self._fetch_recent())
        all_raw.extend(self._fetch_latest())

        new_count, high_count = self._process(all_raw)

        self.last_poll_time = datetime.now()
        self.last_error     = None

        summary = {
            "poll_number": self.poll_count,
            "fetched":     len(all_raw),
            "new":         new_count,
            "high_mag":    high_count,
            "time":        self.last_poll_time.isoformat(),
        }
        logger.info(
            f"✔ Poll #{self.poll_count} selesai — "
            f"{len(all_raw)} data fetched, {new_count} baru, {high_count} M≥{MAGNITUDE_THRESHOLD}"
        )
        return summary

    # ─────────────────────────────────────────────────────────
    #  Background Thread
    # ─────────────────────────────────────────────────────────

    def _run_loop(self):
        """Loop polling (berjalan di background thread)."""
        logger.info(
            f"🛰  Monitoring Agent aktif | interval={POLL_INTERVAL_SECONDS}s "
            f"| threshold=M≥{MAGNITUDE_THRESHOLD}"
        )
        while self.is_running:
            try:
                self.poll_once()
            except Exception as exc:
                self.last_error = str(exc)
                logger.error(f"Error di polling loop: {exc}")

            if self.is_running:
                logger.info(f"⏱  Polling berikutnya dalam {POLL_INTERVAL_SECONDS} detik ...")
                # Tidur dalam potongan kecil agar bisa dihentikan lebih cepat
                for _ in range(POLL_INTERVAL_SECONDS):
                    if not self.is_running:
                        break
                    time.sleep(1)

        logger.info("🔴 Monitoring Agent dihentikan.")

    def start(self):
        """Mulai polling di background thread (non-blocking)."""
        if self._thread and self._thread.is_alive():
            logger.warning("Monitoring Agent sudah berjalan.")
            return
        self.is_running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name="MonitoringAgent",
            daemon=True,
        )
        self._thread.start()
        logger.info(f"Thread '{self._thread.name}' dimulai (daemon=True).")

    def stop(self):
        """Hentikan polling loop."""
        self.is_running = False
        logger.info("Sinyal stop dikirim ke Monitoring Agent.")

    # ─────────────────────────────────────────────────────────
    #  Status (untuk API)
    # ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "is_running":        self.is_running,
            "last_poll_time":    self.last_poll_time.isoformat() if self.last_poll_time else None,
            "poll_count":        self.poll_count,
            "poll_interval_sec": POLL_INTERVAL_SECONDS,
            "magnitude_threshold": MAGNITUDE_THRESHOLD,
            "last_error":        self.last_error,
        }


# ─────────────────────────────────────────────────────────────
#  Jalankan standalone untuk testing
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agent = MonitoringAgent()
    result = agent.poll_once()
    print("\n=== Hasil Poll ===")
    for k, v in result.items():
        print(f"  {k:15}: {v}")
