"""
app.py — CEPAT Dashboard (Flask)
Fase 1: monitoring + acknowledge
Fase 2: pipeline trigger, situation reports, intelligence reports
Fase 3: approval queue, communication drafts, coordination plans, audit log
"""

import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, jsonify, request
from database.db_handler import DatabaseHandler
from agents.orchestrator import Orchestrator
from config import FLASK_SECRET_KEY, FLASK_DEBUG, FLASK_PORT, FLASK_HOST

# ─────────────────────────────────────────────────────────────
#  App & Logger
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Dashboard")

# ─────────────────────────────────────────────────────────────
#  Inisialisasi layanan
# ─────────────────────────────────────────────────────────────
db          = DatabaseHandler()
orchestrator = Orchestrator(db_handler=db)


# ─────────────────────────────────────────────────────────────
#  Halaman Utama
# ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─────────────────────────────────────────────────────────────
#  REST API — Earthquakes (Fase 1)
# ─────────────────────────────────────────────────────────────
@app.route("/api/earthquakes")
def api_get_earthquakes():
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))
    data  = db.get_all_earthquakes(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/earthquakes/<int:eq_id>/acknowledge", methods=["POST"])
def api_acknowledge(eq_id: int):
    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Gempa tidak ditemukan"}), 404
    if eq["status"] == "ACKNOWLEDGED":
        return jsonify({"status": "ok", "message": "Sudah ACKNOWLEDGED"})
    success = db.acknowledge_earthquake(eq_id)
    if success:
        return jsonify({"status": "success", "message": f"Gempa {eq_id} berhasil diakui", "id": eq_id})
    return jsonify({"status": "error", "message": "Gagal update database"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Stats & Orchestrator Status
# ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    stats  = db.get_stats()
    status = orchestrator.get_status()
    return jsonify({
        "status": "success",
        "data": {
            **stats,
            "agent":       status,
            "server_time": datetime.now().isoformat(),
        },
    })


@app.route("/api/agent/poll", methods=["POST"])
def api_force_poll():
    """Paksa satu siklus Monitoring + Pipeline sekarang."""
    try:
        poll_result = orchestrator.monitoring_agent.poll_once()
        pipeline_results = orchestrator.process_pending_events()
        return jsonify({
            "status": "success",
            "data": {
                "poll":     poll_result,
                "pipeline": pipeline_results,
            },
        })
    except Exception as e:
        logger.error(f"Error saat force poll: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Situation Reports (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/situation-reports")
def api_get_sitreps():
    """GET /api/situation-reports?limit=20 — semua sitrep terbaru."""
    limit = request.args.get("limit", 20, type=int)
    data  = db.get_all_situation_reports(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/situation-reports/<int:eq_id>")
def api_get_sitrep(eq_id: int):
    """GET /api/situation-reports/<eq_id> — sitrep untuk satu gempa."""
    sitrep = db.get_situation_report(eq_id)
    if sitrep is None:
        return jsonify({"status": "not_found", "message": "Sitrep belum dibuat"}), 404
    return jsonify({"status": "success", "data": sitrep})


# ─────────────────────────────────────────────────────────────
#  REST API — Intelligence Reports (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/intelligence")
def api_get_intel():
    """GET /api/intelligence?limit=50 — semua intel reports terbaru."""
    limit = request.args.get("limit", 50, type=int)
    data  = db.get_all_intelligence_reports(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/intelligence/<int:eq_id>")
def api_get_intel_for_eq(eq_id: int):
    """GET /api/intelligence/<eq_id> — intel reports untuk satu gempa."""
    data = db.get_intelligence_reports(eq_id)
    return jsonify({"status": "success", "count": len(data), "data": data})


# ─────────────────────────────────────────────────────────────
#  REST API — Pipeline Trigger (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/pipeline/<int:eq_id>", methods=["POST"])
def api_trigger_pipeline(eq_id: int):
    """POST /api/pipeline/<eq_id> — paksa pipeline untuk satu gempa."""
    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Gempa tidak ditemukan"}), 404

    # Reset status ke PENDING agar bisa diproses ulang
    db.update_pipeline_status(eq_id, "PENDING")

    try:
        result = orchestrator.run_pipeline_for_earthquake(eq)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error pipeline gempa {eq_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────
#  Halaman Approval Queue (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/approval")
def approval_queue():
    return render_template("approval_queue.html")


# ─────────────────────────────────────────────────────────────
#  REST API — Approval Queue Stats (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/stats")
def api_approval_stats():
    return jsonify({"status": "success", "data": db.get_approval_stats()})


# ─────────────────────────────────────────────────────────────
#  REST API — Communication Drafts (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/drafts")
def api_get_drafts():
    data = db.get_all_communication_drafts(limit=100)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/drafts/pending")
def api_get_pending_drafts():
    data = db.get_all_pending_drafts(limit=50)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/draft/<int:draft_id>/approve", methods=["POST"])
def api_approve_draft(draft_id: int):
    body         = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", "Petugas BPBD")

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draf tidak ditemukan"}), 404

    success = db.approve_communication_draft(draft_id, officer_name)
    if success:
        db.insert_audit_log({
            "action_type":  "APPROVE",
            "item_table":   "communication_drafts",
            "item_id":      draft_id,
            "decision":     "APPROVED",
            "officer_name": officer_name,
            "notes":        body.get("notes", ""),
        })
        return jsonify({"status": "success", "message": f"Draf {draft_id} disetujui"})
    return jsonify({"status": "error", "message": "Gagal approve draf"}), 500


@app.route("/api/approval/draft/<int:draft_id>/reject", methods=["POST"])
def api_reject_draft(draft_id: int):
    body         = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", "Petugas BPBD")
    notes        = body.get("notes", "")

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draf tidak ditemukan"}), 404

    success = db.reject_communication_draft(draft_id, officer_name)
    if success:
        db.insert_audit_log({
            "action_type":  "REJECT",
            "item_table":   "communication_drafts",
            "item_id":      draft_id,
            "decision":     "REJECTED",
            "officer_name": officer_name,
            "notes":        notes,
        })
        return jsonify({"status": "success", "message": f"Draf {draft_id} ditolak"})
    return jsonify({"status": "error", "message": "Gagal reject draf"}), 500


@app.route("/api/approval/draft/<int:draft_id>/edit", methods=["POST"])
def api_edit_draft(draft_id: int):
    body         = request.get_json(silent=True) or {}
    new_content  = body.get("content", "").strip()
    officer_name = body.get("officer_name", "Petugas BPBD")

    if not new_content:
        return jsonify({"status": "error", "message": "Konten tidak boleh kosong"}), 400

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draf tidak ditemukan"}), 404

    success = db.edit_communication_draft(draft_id, new_content)
    if success:
        db.insert_audit_log({
            "action_type":  "EDIT",
            "item_table":   "communication_drafts",
            "item_id":      draft_id,
            "decision":     "EDITED",
            "officer_name": officer_name,
            "notes":        f"Konten diedit: {new_content[:80]}…",
        })
        return jsonify({"status": "success", "message": f"Draf {draft_id} diedit"})
    return jsonify({"status": "error", "message": "Gagal edit draf"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Coordination Plans (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/plans")
def api_get_plans():
    data = db.get_all_coordination_plans(limit=50)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/plans/pending")
def api_get_pending_plans():
    data = db.get_all_pending_coordination_plans(limit=50)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/plan/<int:plan_id>/approve", methods=["POST"])
def api_approve_plan(plan_id: int):
    body         = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", "Petugas BPBD")

    plan = db.get_coordination_plan_by_id(plan_id)
    if plan is None:
        return jsonify({"status": "error", "message": "Plan tidak ditemukan"}), 404

    success = db.approve_coordination_plan(plan_id, officer_name)
    if success:
        db.insert_audit_log({
            "action_type":  "APPROVE",
            "item_table":   "coordination_plans",
            "item_id":      plan_id,
            "decision":     "APPROVED",
            "officer_name": officer_name,
            "notes":        body.get("notes", ""),
        })
        return jsonify({"status": "success", "message": f"Plan {plan_id} disetujui"})
    return jsonify({"status": "error", "message": "Gagal approve plan"}), 500


@app.route("/api/approval/plan/<int:plan_id>/reject", methods=["POST"])
def api_reject_plan(plan_id: int):
    body         = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", "Petugas BPBD")
    notes        = body.get("notes", "")

    plan = db.get_coordination_plan_by_id(plan_id)
    if plan is None:
        return jsonify({"status": "error", "message": "Plan tidak ditemukan"}), 404

    success = db.reject_coordination_plan(plan_id, officer_name)
    if success:
        db.insert_audit_log({
            "action_type":  "REJECT",
            "item_table":   "coordination_plans",
            "item_id":      plan_id,
            "decision":     "REJECTED",
            "officer_name": officer_name,
            "notes":        notes,
        })
        return jsonify({"status": "success", "message": f"Plan {plan_id} ditolak"})
    return jsonify({"status": "error", "message": "Gagal reject plan"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Audit Log (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/audit-log")
def api_audit_log():
    limit = request.args.get("limit", 50, type=int)
    data  = db.get_audit_log(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


# ─────────────────────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Endpoint tidak ditemukan"}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"status": "error", "message": "Internal server error"}), 500


# ─────────────────────────────────────────────────────────────
#  Entry Point
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("  CEPAT — Emergency Monitoring System")
    logger.info("  Fase 3: Full Pipeline + Human-in-the-Loop")
    logger.info("=" * 60)

    orchestrator.start()

    logger.info(f"Dashboard berjalan di http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        use_reloader=False,
    )
