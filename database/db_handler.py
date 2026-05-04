"""
db_handler.py — Database Layer CEPAT
Mengelola semua operasi SQLite: init, insert, query, update.
Fase 1: earthquakes
Fase 2: intelligence_reports, situation_reports, pipeline_status
"""

import sqlite3
import os
import sys
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class DatabaseHandler:
    """
    Handler tunggal untuk semua operasi database CEPAT.
    Thread-safe: setiap operasi membuat koneksi baru.
    """

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_db()
        self._run_migrations()

    # ─────────────────────────────────────────────────────────
    #  Koneksi
    # ─────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # ─────────────────────────────────────────────────────────
    #  Init & Migration
    # ─────────────────────────────────────────────────────────

    def init_db(self):
        """Buat tabel dan indeks jika belum ada."""
        try:
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            with self._connect() as conn:
                conn.executescript(schema_sql)
            logger.info(f"Database diinisialisasi: {self.db_path}")
        except Exception as e:
            logger.error(f"Gagal inisialisasi database: {e}")
            raise

    def _run_migrations(self):
        """Migrasi skema untuk database yang sudah ada (Fase 1 → Fase 2 → Fase 3)."""
        migrations = [
            # Fase 1 → Fase 2
            "ALTER TABLE earthquakes ADD COLUMN pipeline_status TEXT DEFAULT 'PENDING'",
            "CREATE INDEX IF NOT EXISTS idx_earthquakes_pipeline ON earthquakes(pipeline_status)",
            # Fase 2 → Fase 3 (tabel baru dibuat via schema.sql IF NOT EXISTS)
            "CREATE INDEX IF NOT EXISTS idx_commdraft_eq     ON communication_drafts(earthquake_id)",
            "CREATE INDEX IF NOT EXISTS idx_commdraft_status ON communication_drafts(status)",
            "CREATE INDEX IF NOT EXISTS idx_coordplan_eq     ON coordination_plans(earthquake_id)",
            "CREATE INDEX IF NOT EXISTS idx_coordplan_status ON coordination_plans(status)",
        ]
        with self._connect() as conn:
            for sql in migrations:
                try:
                    conn.execute(sql)
                    logger.info(f"Migration applied: {sql[:60]}…")
                except sqlite3.OperationalError:
                    pass  # Kolom/index sudah ada, lewati

    # ─────────────────────────────────────────────────────────
    #  FASE 1 — Earthquakes
    # ─────────────────────────────────────────────────────────

    def insert_earthquake(self, eq: dict) -> bool:
        sql = """
            INSERT OR IGNORE INTO earthquakes
                (event_id, magnitude, depth_km, latitude, longitude,
                 location_desc, timestamp, felt_area, tsunami_potential, status, pipeline_status)
            VALUES
                (:event_id, :magnitude, :depth_km, :latitude, :longitude,
                 :location_desc, :timestamp, :felt_area, :tsunami_potential, 'NEW', :pipeline_status)
        """
        from config import PIPELINE_MIN_MAGNITUDE
        pipeline_status = 'PENDING' if eq.get('magnitude', 0) >= PIPELINE_MIN_MAGNITUDE else 'SKIPPED'
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, {
                    "event_id":          eq.get("event_id", ""),
                    "magnitude":         eq.get("magnitude", 0.0),
                    "depth_km":          eq.get("depth_km", 0.0),
                    "latitude":          eq.get("latitude", 0.0),
                    "longitude":         eq.get("longitude", 0.0),
                    "location_desc":     eq.get("location_desc", ""),
                    "timestamp":         eq.get("timestamp", ""),
                    "felt_area":         eq.get("felt_area", ""),
                    "tsunami_potential": eq.get("tsunami_potential", ""),
                    "pipeline_status":   pipeline_status,
                })
                return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Gagal insert gempa {eq.get('event_id')}: {e}")
            return False

    def acknowledge_earthquake(self, eq_id: int) -> bool:
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE earthquakes SET status = 'ACKNOWLEDGED' WHERE id = ?", (eq_id,)
                )
            logger.info(f"Gempa ID {eq_id} diakui (ACKNOWLEDGED)")
            return True
        except Exception as e:
            logger.error(f"Gagal acknowledge gempa {eq_id}: {e}")
            return False

    def get_all_earthquakes(self, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM earthquakes ORDER BY timestamp DESC, created_at DESC LIMIT ?"
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil data gempa: {e}")
            return []

    def get_earthquake_by_id(self, eq_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM earthquakes WHERE id = ?", (eq_id,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Gagal mengambil gempa ID {eq_id}: {e}")
            return None

    def get_stats(self) -> dict:
        try:
            with self._connect() as conn:
                total      = conn.execute("SELECT COUNT(*) FROM earthquakes").fetchone()[0]
                high_mag   = conn.execute("SELECT COUNT(*) FROM earthquakes WHERE magnitude >= 5.0").fetchone()[0]
                new_count  = conn.execute("SELECT COUNT(*) FROM earthquakes WHERE status = 'NEW'").fetchone()[0]
                sitrep_cnt = conn.execute("SELECT COUNT(*) FROM situation_reports").fetchone()[0]
                latest_row = conn.execute(
                    "SELECT * FROM earthquakes ORDER BY timestamp DESC, created_at DESC LIMIT 1"
                ).fetchone()
            return {
                "total":          total,
                "high_magnitude": high_mag,
                "new_alerts":     new_count,
                "sitrep_count":   sitrep_cnt,
                "latest":         dict(latest_row) if latest_row else None,
            }
        except Exception as e:
            logger.error(f"Gagal mengambil statistik: {e}")
            return {"total": 0, "high_magnitude": 0, "new_alerts": 0, "sitrep_count": 0, "latest": None}

    # ─────────────────────────────────────────────────────────
    #  FASE 2 — Pipeline Status
    # ─────────────────────────────────────────────────────────

    def get_pending_earthquakes(self, min_magnitude: float = 5.0) -> list[dict]:
        """Ambil gempa M≥threshold dengan pipeline_status='PENDING'."""
        sql = """
            SELECT * FROM earthquakes
            WHERE pipeline_status = 'PENDING' AND magnitude >= ?
            ORDER BY magnitude DESC, timestamp DESC
        """
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (min_magnitude,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil pending earthquakes: {e}")
            return []

    def update_pipeline_status(self, eq_id: int, status: str) -> bool:
        """Update pipeline_status: PENDING | PROCESSING | DONE | FAILED | SKIPPED."""
        try:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE earthquakes SET pipeline_status = ? WHERE id = ?", (status, eq_id)
                )
            return True
        except Exception as e:
            logger.error(f"Gagal update pipeline_status gempa {eq_id}: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    #  FASE 2 — Intelligence Reports
    # ─────────────────────────────────────────────────────────

    def insert_intelligence_report(self, report: dict) -> int | None:
        """Simpan satu intelligence report. Return ID baru, atau None jika gagal."""
        sql = """
            INSERT INTO intelligence_reports
                (earthquake_id, source_name, source_url, source_type,
                 title, content, credibility_status, llm_reasoning, published_at)
            VALUES
                (:earthquake_id, :source_name, :source_url, :source_type,
                 :title, :content, :credibility_status, :llm_reasoning, :published_at)
        """
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, {
                    "earthquake_id":      report.get("earthquake_id"),
                    "source_name":        report.get("source_name", ""),
                    "source_url":         report.get("source_url", ""),
                    "source_type":        report.get("source_type", "news_rss"),
                    "title":              report.get("title", ""),
                    "content":            report.get("content", ""),
                    "credibility_status": report.get("credibility_status", "UNVERIFIED"),
                    "llm_reasoning":      report.get("llm_reasoning", ""),
                    "published_at":       report.get("published_at", ""),
                })
                return cur.lastrowid
        except Exception as e:
            logger.error(f"Gagal insert intelligence report: {e}")
            return None

    def get_intelligence_reports(self, earthquake_id: int) -> list[dict]:
        """Ambil semua intelligence reports untuk satu gempa."""
        sql = """
            SELECT * FROM intelligence_reports
            WHERE earthquake_id = ?
            ORDER BY credibility_status ASC, created_at DESC
        """
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (earthquake_id,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil intel reports untuk gempa {earthquake_id}: {e}")
            return []

    def get_all_intelligence_reports(self, limit: int = 50) -> list[dict]:
        """Ambil semua intelligence reports terbaru."""
        sql = "SELECT * FROM intelligence_reports ORDER BY created_at DESC LIMIT ?"
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil semua intel reports: {e}")
            return []

    # ─────────────────────────────────────────────────────────
    #  FASE 2 — Situation Reports
    # ─────────────────────────────────────────────────────────

    def insert_situation_report(self, report: dict) -> bool:
        """Simpan atau update situation report untuk satu gempa."""
        sql = """
            INSERT INTO situation_reports
                (earthquake_id, summary, affected_areas, risk_level,
                 risk_justification, recommendations, notes, raw_llm_output, generated_by)
            VALUES
                (:earthquake_id, :summary, :affected_areas, :risk_level,
                 :risk_justification, :recommendations, :notes, :raw_llm_output, :generated_by)
            ON CONFLICT(earthquake_id) DO UPDATE SET
                summary           = excluded.summary,
                affected_areas    = excluded.affected_areas,
                risk_level        = excluded.risk_level,
                risk_justification = excluded.risk_justification,
                recommendations   = excluded.recommendations,
                notes             = excluded.notes,
                raw_llm_output    = excluded.raw_llm_output,
                generated_by      = excluded.generated_by,
                created_at        = CURRENT_TIMESTAMP
        """
        recs = report.get("recommendations", [])
        recs_json = json.dumps(recs, ensure_ascii=False) if isinstance(recs, list) else recs

        try:
            with self._connect() as conn:
                conn.execute(sql, {
                    "earthquake_id":      report.get("earthquake_id"),
                    "summary":            report.get("summary", ""),
                    "affected_areas":     report.get("affected_areas", ""),
                    "risk_level":         report.get("risk_level", "MEDIUM"),
                    "risk_justification": report.get("risk_justification", ""),
                    "recommendations":    recs_json,
                    "notes":              report.get("notes", ""),
                    "raw_llm_output":     report.get("raw_llm_output", ""),
                    "generated_by":       report.get("generated_by", "llm"),
                })
            return True
        except Exception as e:
            logger.error(f"Gagal insert situation report: {e}")
            return False

    def get_situation_report(self, earthquake_id: int) -> dict | None:
        """Ambil situation report untuk satu gempa."""
        sql = """
            SELECT sr.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM situation_reports sr
            JOIN earthquakes eq ON sr.earthquake_id = eq.id
            WHERE sr.earthquake_id = ?
        """
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (earthquake_id,)).fetchone()
            if row:
                d = dict(row)
                # Parse recommendations JSON
                try:
                    d["recommendations"] = json.loads(d.get("recommendations", "[]"))
                except Exception:
                    d["recommendations"] = []
                return d
            return None
        except Exception as e:
            logger.error(f"Gagal mengambil sitrep gempa {earthquake_id}: {e}")
            return None

    def get_all_situation_reports(self, limit: int = 20) -> list[dict]:
        """Ambil semua situation reports terbaru (dengan info gempa)."""
        sql = """
            SELECT sr.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM situation_reports sr
            JOIN earthquakes eq ON sr.earthquake_id = eq.id
            ORDER BY sr.created_at DESC
            LIMIT ?
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["recommendations"] = json.loads(d.get("recommendations", "[]"))
                except Exception:
                    d["recommendations"] = []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Gagal mengambil semua sitrep: {e}")
            return []

    # ─────────────────────────────────────────────────────────
    #  FASE 3 — Communication Drafts
    # ─────────────────────────────────────────────────────────

    def insert_communication_draft(self, draft: dict) -> int | None:
        sql = """
            INSERT INTO communication_drafts
                (situation_report_id, earthquake_id, draft_type, content, status)
            VALUES
                (:situation_report_id, :earthquake_id, :draft_type, :content, 'DRAFT')
        """
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, {
                    "situation_report_id": draft.get("situation_report_id"),
                    "earthquake_id":       draft.get("earthquake_id"),
                    "draft_type":          draft.get("draft_type", ""),
                    "content":             draft.get("content", ""),
                })
                return cur.lastrowid
        except Exception as e:
            logger.error(f"Gagal insert communication draft: {e}")
            return None

    def get_communication_drafts(self, earthquake_id: int) -> list[dict]:
        sql = """
            SELECT cd.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM communication_drafts cd
            JOIN earthquakes eq ON cd.earthquake_id = eq.id
            WHERE cd.earthquake_id = ?
            ORDER BY cd.draft_type
        """
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (earthquake_id,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil drafts gempa {earthquake_id}: {e}")
            return []

    def get_all_pending_drafts(self, limit: int = 50) -> list[dict]:
        sql = """
            SELECT cd.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM communication_drafts cd
            JOIN earthquakes eq ON cd.earthquake_id = eq.id
            WHERE cd.status = 'DRAFT'
            ORDER BY cd.created_at DESC
            LIMIT ?
        """
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil pending drafts: {e}")
            return []

    def get_all_communication_drafts(self, limit: int = 100) -> list[dict]:
        sql = """
            SELECT cd.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM communication_drafts cd
            JOIN earthquakes eq ON cd.earthquake_id = eq.id
            ORDER BY cd.created_at DESC
            LIMIT ?
        """
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(sql, (limit,)).fetchall()]
        except Exception as e:
            logger.error(f"Gagal mengambil communication drafts: {e}")
            return []

    def approve_communication_draft(self, draft_id: int, officer_name: str = "Petugas BPBD") -> bool:
        sql = "UPDATE communication_drafts SET status='APPROVED', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            with self._connect() as conn:
                conn.execute(sql, (officer_name, draft_id))
            return True
        except Exception as e:
            logger.error(f"Gagal approve draft {draft_id}: {e}")
            return False

    def reject_communication_draft(self, draft_id: int, officer_name: str = "Petugas BPBD") -> bool:
        sql = "UPDATE communication_drafts SET status='REJECTED', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            with self._connect() as conn:
                conn.execute(sql, (officer_name, draft_id))
            return True
        except Exception as e:
            logger.error(f"Gagal reject draft {draft_id}: {e}")
            return False

    def edit_communication_draft(self, draft_id: int, new_content: str) -> bool:
        try:
            with self._connect() as conn:
                conn.execute("UPDATE communication_drafts SET content=? WHERE id=?", (new_content, draft_id))
            return True
        except Exception as e:
            logger.error(f"Gagal edit draft {draft_id}: {e}")
            return False

    def get_communication_draft_by_id(self, draft_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM communication_drafts WHERE id=?", (draft_id,)).fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Gagal ambil draft {draft_id}: {e}")
            return None

    # ─────────────────────────────────────────────────────────
    #  FASE 3 — Coordination Plans
    # ─────────────────────────────────────────────────────────

    def insert_coordination_plan(self, plan: dict) -> int | None:
        sql = """
            INSERT INTO coordination_plans
                (situation_report_id, earthquake_id, resource_mapping,
                 action_priorities, estimated_timeline, generated_by, status)
            VALUES
                (:situation_report_id, :earthquake_id, :resource_mapping,
                 :action_priorities, :estimated_timeline, :generated_by, 'DRAFT')
        """
        priorities = plan.get("action_priorities", [])
        if isinstance(priorities, list):
            priorities = json.dumps(priorities, ensure_ascii=False)
        try:
            with self._connect() as conn:
                cur = conn.execute(sql, {
                    "situation_report_id": plan.get("situation_report_id"),
                    "earthquake_id":       plan.get("earthquake_id"),
                    "resource_mapping":    plan.get("resource_mapping", ""),
                    "action_priorities":   priorities,
                    "estimated_timeline":  plan.get("estimated_timeline", ""),
                    "generated_by":        plan.get("generated_by", "llm"),
                })
                return cur.lastrowid
        except Exception as e:
            logger.error(f"Gagal insert coordination plan: {e}")
            return None

    def get_coordination_plan(self, earthquake_id: int) -> dict | None:
        sql = """
            SELECT cp.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM coordination_plans cp
            JOIN earthquakes eq ON cp.earthquake_id = eq.id
            WHERE cp.earthquake_id = ?
            ORDER BY cp.created_at DESC
            LIMIT 1
        """
        try:
            with self._connect() as conn:
                row = conn.execute(sql, (earthquake_id,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["action_priorities"] = json.loads(d.get("action_priorities", "[]"))
                except Exception:
                    d["action_priorities"] = []
                return d
            return None
        except Exception as e:
            logger.error(f"Gagal ambil coordination plan gempa {earthquake_id}: {e}")
            return None

    def get_coordination_plan_by_id(self, plan_id: int) -> dict | None:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM coordination_plans WHERE id=?", (plan_id,)).fetchone()
            if row:
                d = dict(row)
                try:
                    d["action_priorities"] = json.loads(d.get("action_priorities", "[]"))
                except Exception:
                    d["action_priorities"] = []
                return d
            return None
        except Exception as e:
            logger.error(f"Gagal ambil plan {plan_id}: {e}")
            return None

    def get_all_pending_coordination_plans(self, limit: int = 50) -> list[dict]:
        sql = """
            SELECT cp.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM coordination_plans cp
            JOIN earthquakes eq ON cp.earthquake_id = eq.id
            WHERE cp.status = 'DRAFT'
            ORDER BY cp.created_at DESC
            LIMIT ?
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["action_priorities"] = json.loads(d.get("action_priorities", "[]"))
                except Exception:
                    d["action_priorities"] = []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Gagal ambil pending plans: {e}")
            return []

    def get_all_coordination_plans(self, limit: int = 50) -> list[dict]:
        sql = """
            SELECT cp.*, eq.magnitude, eq.location_desc, eq.timestamp as eq_timestamp
            FROM coordination_plans cp
            JOIN earthquakes eq ON cp.earthquake_id = eq.id
            ORDER BY cp.created_at DESC
            LIMIT ?
        """
        try:
            with self._connect() as conn:
                rows = conn.execute(sql, (limit,)).fetchall()
            result = []
            for row in rows:
                d = dict(row)
                try:
                    d["action_priorities"] = json.loads(d.get("action_priorities", "[]"))
                except Exception:
                    d["action_priorities"] = []
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Gagal ambil coordination plans: {e}")
            return []

    def approve_coordination_plan(self, plan_id: int, officer_name: str = "Petugas BPBD") -> bool:
        sql = "UPDATE coordination_plans SET status='APPROVED', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            with self._connect() as conn:
                conn.execute(sql, (officer_name, plan_id))
            return True
        except Exception as e:
            logger.error(f"Gagal approve plan {plan_id}: {e}")
            return False

    def reject_coordination_plan(self, plan_id: int, officer_name: str = "Petugas BPBD") -> bool:
        sql = "UPDATE coordination_plans SET status='REJECTED', approved_by=?, approved_at=CURRENT_TIMESTAMP WHERE id=?"
        try:
            with self._connect() as conn:
                conn.execute(sql, (officer_name, plan_id))
            return True
        except Exception as e:
            logger.error(f"Gagal reject plan {plan_id}: {e}")
            return False

    # ─────────────────────────────────────────────────────────
    #  FASE 3 — Audit Log
    # ─────────────────────────────────────────────────────────

    def insert_audit_log(self, entry: dict) -> bool:
        sql = """
            INSERT INTO audit_log
                (action_type, item_table, item_id, decision, officer_name, notes)
            VALUES
                (:action_type, :item_table, :item_id, :decision, :officer_name, :notes)
        """
        try:
            with self._connect() as conn:
                conn.execute(sql, {
                    "action_type":  entry.get("action_type", "APPROVE"),
                    "item_table":   entry.get("item_table", ""),
                    "item_id":      entry.get("item_id"),
                    "decision":     entry.get("decision", ""),
                    "officer_name": entry.get("officer_name", "Petugas BPBD"),
                    "notes":        entry.get("notes", ""),
                })
            return True
        except Exception as e:
            logger.error(f"Gagal insert audit log: {e}")
            return False

    def get_audit_log(self, limit: int = 50) -> list[dict]:
        try:
            with self._connect() as conn:
                return [dict(r) for r in conn.execute(
                    "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
                ).fetchall()]
        except Exception as e:
            logger.error(f"Gagal ambil audit log: {e}")
            return []

    # ─────────────────────────────────────────────────────────
    #  FASE 3 — Approval Queue Stats
    # ─────────────────────────────────────────────────────────

    def get_approval_stats(self) -> dict:
        try:
            with self._connect() as conn:
                pending_drafts = conn.execute(
                    "SELECT COUNT(*) FROM communication_drafts WHERE status='DRAFT'"
                ).fetchone()[0]
                pending_plans = conn.execute(
                    "SELECT COUNT(*) FROM coordination_plans WHERE status='DRAFT'"
                ).fetchone()[0]
                approved_today = conn.execute(
                    "SELECT COUNT(*) FROM audit_log WHERE decision='APPROVED' AND date(timestamp)=date('now')"
                ).fetchone()[0]
            return {
                "pending_drafts":  pending_drafts,
                "pending_plans":   pending_plans,
                "total_pending":   pending_drafts + pending_plans,
                "approved_today":  approved_today,
            }
        except Exception as e:
            logger.error(f"Gagal ambil approval stats: {e}")
            return {"pending_drafts": 0, "pending_plans": 0, "total_pending": 0, "approved_today": 0}
