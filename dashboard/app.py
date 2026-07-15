"""
app.py — CEPAT Dashboard (Flask)
Fase 1: monitoring + acknowledge
Fase 2: pipeline trigger, situation reports, intelligence reports
Fase 3: approval queue, communication drafts, coordination plans, audit log
"""

# Auto-reload trigger for reportlab detection
import logging
import os
import sys
from datetime import datetime
from functools import wraps

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, redirect, render_template, request, send_from_directory, session, url_for
from flask_socketio import SocketIO

from agents.orchestrator import Orchestrator
from config import FLASK_DEBUG, FLASK_HOST, FLASK_PORT, FLASK_SECRET_KEY, OPERATORS
from database.db_handler import DatabaseHandler

# ─────────────────────────────────────────────────────────────
#  App & Logger
# ─────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = FLASK_SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("Dashboard")

# ─────────────────────────────────────────────────────────────
#  Inisialisasi layanan
# ─────────────────────────────────────────────────────────────
db = DatabaseHandler()

def broadcast_socket_event(event, data):
    try:
        socketio.emit(event, data)
        logger.info(f"[WebSocket] Broadcasted '{event}': {data}")
    except Exception as e:
        logger.error(f"[WebSocket] Failed to broadcast '{event}': {e}")

orchestrator = Orchestrator(db_handler=db, on_event=broadcast_socket_event)

# Seed operator accounts from config (first startup only)
try:
    db.seed_operators_from_config(OPERATORS)
except Exception as _e:
    logger.warning(f"Could not seed operators: {_e}")


# ─────────────────────────────────────────────────────────────
#  Authentication (T2.3)
# ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("operator"):
            # API endpoints return JSON, page routes redirect
            if request.path.startswith("/api/"):
                return jsonify({"status": "error", "message": "Login required"}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)

    return decorated


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("operator"):
        return redirect(url_for("index"))
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        # Try DB-based auth first
        op = db.get_operator_by_username(username)
        auth_ok = False
        if op:
            auth_ok = db.verify_password(password, op["password_hash"])
            if auth_ok:
                db.update_last_login(username)
                session["operator"] = username
                session["role"] = op.get("role", "operator")
                session["full_name"] = op.get("full_name", username)
        elif username in OPERATORS and OPERATORS[username] == password:
            # Fallback to config (backward compat)
            auth_ok = True
            session["operator"] = username
            session["role"] = "admin" if username == "admin" else "operator"
            session["full_name"] = username
        if auth_ok:
            session.permanent = True
            logger.info(f"Login berhasil: {username}")
            return redirect(url_for("index"))
        error = "Invalid username or password."
        logger.warning(f"Login gagal untuk username: {username}")
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    operator = session.pop("operator", None)
    if operator:
        logger.info(f"Logout: {operator}")
    return redirect(url_for("login_page"))


@app.route("/sw.js")
def service_worker():
    response = send_from_directory(os.path.join(app.root_path, "static"), "sw.js")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


# ─────────────────────────────────────────────────────────────
#  Halaman Utama
# ─────────────────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    from flask import make_response
    resp = make_response(render_template("dashboard_v5.html"))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ─────────────────────────────────────────────────────────────
#  REST API — Earthquakes (Fase 1)
# ─────────────────────────────────────────────────────────────
@app.route("/api/earthquakes")
@login_required
def api_get_earthquakes():
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))
    data = db.get_all_earthquakes(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/earthquakes/hourly")
@login_required
def api_earthquakes_hourly():
    """GET /api/earthquakes/hourly — jumlah gempa per jam dalam 24 jam terakhir."""
    try:
        with db._connect() as conn:
            rows = conn.execute("""
                SELECT
                    CAST(strftime('%H', created_at) AS INTEGER) AS hour,
                    COUNT(*) AS count,
                    MAX(magnitude) AS max_mag
                FROM earthquakes
                WHERE created_at >= datetime('now', '-24 hours')
                GROUP BY hour
                ORDER BY hour ASC
            """).fetchall()
        hourly = {
            r["hour"]: {"count": r["count"], "max_mag": r["max_mag"]} for r in rows
        }
        # Isi jam yang kosong dengan 0
        result = []
        for h in range(24):
            d = hourly.get(h, {"count": 0, "max_mag": 0})
            result.append(
                {"hour": h, "count": d["count"], "max_mag": d["max_mag"] or 0}
            )
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error hourly stats: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Laporan Lengkap (T2.4)
# ─────────────────────────────────────────────────────────────
@app.route("/api/earthquakes/major")
@login_required
def api_get_major_earthquakes():
    """GET /api/earthquakes/major — gempa M>=5 untuk halaman laporan."""
    try:
        with db._connect() as conn:
            rows = conn.execute("""
                SELECT * FROM earthquakes
                WHERE magnitude >= 5.0
                ORDER BY timestamp DESC, created_at DESC
                LIMIT 50
            """).fetchall()
        data = [dict(r) for r in rows]
        return jsonify({"status": "success", "count": len(data), "data": data})
    except Exception as e:
        logger.error(f"Error major earthquakes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/earthquakes/<int:eq_id>/acknowledge", methods=["POST"])
@login_required
def api_acknowledge(eq_id: int):
    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Earthquake not found"}), 404
    if eq["status"] == "ACKNOWLEDGED":
        return jsonify({"status": "ok", "message": "Sudah ACKNOWLEDGED"})
    success = db.acknowledge_earthquake(eq_id)
    if success:
        return jsonify(
            {
                "status": "success",
                "message": f"Gempa {eq_id} berhasil diakui",
                "id": eq_id,
            }
        )
    return jsonify({"status": "error", "message": "Gagal update database"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Stats & Orchestrator Status
# ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
@login_required
def api_stats():
    stats = db.get_stats()
    status = orchestrator.get_status()
    # Tambahkan field yang dibutuhkan frontend
    agent_formatted = {
        **status,
        "mode": "ACTIVE" if status.get("is_running") else "STANDBY",
        "cycles": status.get("cycle_count", 0),
    }
    return jsonify(
        {
            "status": "success",
            "data": {
                **stats,
                "agent": agent_formatted,
                "server_time": datetime.now().isoformat(),
            },
        }
    )


@app.route("/api/agent/poll", methods=["POST"])
@login_required
def api_force_poll():
    """Paksa satu siklus Monitoring + Pipeline sekarang."""
    try:
        poll_result = orchestrator.monitoring_agent.poll_once()
        pipeline_results = orchestrator.process_pending_events()
        return jsonify(
            {
                "status": "success",
                "data": {
                    "poll": poll_result,
                    "pipeline": pipeline_results,
                },
            }
        )
    except Exception as e:
        logger.error(f"Error saat force poll: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Activity Feed (Combined)
# ─────────────────────────────────────────────────────────────
@app.route("/api/feed")
@login_required
def api_feed():
    try:
        # 1. Fetch memory-based logs from Orchestrator
        feed = list(orchestrator.activity_logs) if hasattr(orchestrator, "activity_logs") else []

        # 2. Fetch database records for historical backfill
        db_feed = []
        eqs = db.get_all_earthquakes(limit=10)
        intel = db.get_all_intelligence_reports(limit=15)
        drafts = db.get_all_communication_drafts(limit=10)
        
        # situation reports and coordination plans
        sitreps = db.get_all_situation_reports(limit=10)
        plans = db.get_all_coordination_plans(limit=10)

        for e in eqs:
            if e["status"] != "NEW":
                db_feed.append(
                    {
                        "ts": e["created_at"],
                        "ag": "Monitoring Agent",
                        "st": "ok",
                        "d": f"Event terdeteksi: M{e['magnitude']} di {e['location_desc']}",
                    }
                )
        for i in intel:
            st = "ok" if i["credibility_status"] == "VALID" else "wait"
            db_feed.append(
                {
                    "ts": i["created_at"],
                    "ag": "Intelligence Agent",
                    "st": st,
                    "d": f"Analisis [{i['source_name']}]: {i['title'][:40]}... ({i['credibility_status']})",
                }
            )
        for d in drafts:
            db_feed.append(
                {
                    "ts": d["created_at"],
                    "ag": "Communication Agent",
                    "st": "ok",
                    "d": f"Penyusunan draf peringatan selesai (ID: {d['id']})",
                }
            )
        for s in sitreps:
            db_feed.append(
                {
                    "ts": s["created_at"],
                    "ag": "Analysis Agent",
                    "st": "ok",
                    "d": f"Situation Report dibuat. Risk: {s['risk_level']}",
                }
            )
        for p in plans:
            db_feed.append(
                {
                    "ts": p["created_at"],
                    "ag": "Coordination Agent",
                    "st": "ok",
                    "d": f"Rencana koordinasi dibuat (Status: {p['status']})",
                }
            )

        # Remove duplicate log descriptions per agent within the combined list
        combined = feed + db_feed
        seen = set()
        unique_feed = []
        for item in combined:
            key = (item["ts"][:19] if item["ts"] else "", item["ag"], item["d"])
            if key not in seen:
                seen.add(key)
                unique_feed.append(item)

        unique_feed.sort(key=lambda x: x["ts"], reverse=True)
        return jsonify({"status": "success", "data": unique_feed[:30]})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Situation Reports (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/situation-reports")
@login_required
def api_get_sitreps():
    """GET /api/situation-reports?limit=20 — semua sitrep terbaru."""
    limit = request.args.get("limit", 20, type=int)
    data = db.get_all_situation_reports(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/situation-reports/<int:eq_id>")
@login_required
def api_get_sitrep(eq_id: int):
    """GET /api/situation-reports/<eq_id> — sitrep untuk satu gempa."""
    sitrep = db.get_situation_report(eq_id)
    if sitrep is None:
        return jsonify({"status": "not_found", "message": "Sitrep has not been generated"}), 404
    return jsonify({"status": "success", "data": sitrep})


# ─────────────────────────────────────────────────────────────
#  REST API — Intelligence Reports (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/intelligence")
@login_required
def api_get_intel():
    """GET /api/intelligence?limit=50 — semua intel reports terbaru."""
    limit = request.args.get("limit", 50, type=int)
    data = db.get_all_intelligence_reports(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/intelligence/<int:eq_id>")
@login_required
def api_get_intel_for_eq(eq_id: int):
    """GET /api/intelligence/<eq_id> — intel reports untuk satu gempa."""
    data = db.get_intelligence_reports(eq_id)
    return jsonify({"status": "success", "count": len(data), "data": data})


# ─────────────────────────────────────────────────────────────
#  REST API — Pipeline Trigger (Fase 2)
# ─────────────────────────────────────────────────────────────
@app.route("/api/pipeline/<int:eq_id>", methods=["POST"])
@login_required
def api_trigger_pipeline(eq_id: int):
    """POST /api/pipeline/<eq_id> — paksa pipeline untuk satu gempa."""
    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Earthquake not found"}), 404

    # Reset status ke PENDING agar bisa diproses ulang
    db.update_pipeline_status(eq_id, "PENDING")

    try:
        result = orchestrator.run_pipeline_for_earthquake(eq)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        logger.error(f"Error pipeline gempa {eq_id}: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  Halaman Approval Queue (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/approval")
@login_required
def approval_queue():
    return redirect(url_for("index"))


# ─────────────────────────────────────────────────────────────
#  REST API — Approval Queue Stats (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/stats")
@login_required
def api_approval_stats():
    return jsonify({"status": "success", "data": db.get_approval_stats()})


# ─────────────────────────────────────────────────────────────
#  REST API — Communication Drafts (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/drafts")
@login_required
def api_get_drafts():
    data = db.get_all_communication_drafts(limit=100)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/drafts/pending")
@login_required
def api_get_pending_drafts():
    data = db.get_all_pending_drafts(limit=200)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/draft/<int:draft_id>/approve", methods=["POST"])
@login_required
def api_approve_draft(draft_id: int):
    body = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", session.get("operator", "Petugas BPBD"))

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draft not found"}), 404

    success = db.approve_communication_draft(draft_id, officer_name)
    if success:
        db.insert_audit_log(
            {
                "action_type": "APPROVE",
                "item_table": "communication_drafts",
                "item_id": draft_id,
                "decision": "APPROVED",
                "officer_name": officer_name,
                "notes": body.get("notes", ""),
            }
        )
        return jsonify({"status": "success", "message": f"Draft {draft_id} approved"})
    return jsonify({"status": "error", "message": "Failed to approve draft"}), 500


@app.route("/api/approval/draft/<int:draft_id>/reject", methods=["POST"])
@login_required
def api_reject_draft(draft_id: int):
    body = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", session.get("operator", "Petugas BPBD"))
    notes = body.get("notes", "")

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draft not found"}), 404

    success = db.reject_communication_draft(draft_id, officer_name)
    if success:
        db.insert_audit_log(
            {
                "action_type": "REJECT",
                "item_table": "communication_drafts",
                "item_id": draft_id,
                "decision": "REJECTED",
                "officer_name": officer_name,
                "notes": notes,
            }
        )
        return jsonify({"status": "success", "message": f"Draft {draft_id} rejected"})
    return jsonify({"status": "error", "message": "Failed to reject draft"}), 500


@app.route("/api/approval/draft/<int:draft_id>/edit", methods=["POST"])
@login_required
def api_edit_draft(draft_id: int):
    body = request.get_json(silent=True) or {}
    new_content = body.get("content", "").strip()
    officer_name = body.get("officer_name", session.get("operator", "Petugas BPBD"))

    if not new_content:
        return jsonify({"status": "error", "message": "Content cannot be empty"}), 400

    draft = db.get_communication_draft_by_id(draft_id)
    if draft is None:
        return jsonify({"status": "error", "message": "Draft not found"}), 404

    success = db.edit_communication_draft(draft_id, new_content)
    if success:
        db.insert_audit_log(
            {
                "action_type": "EDIT",
                "item_table": "communication_drafts",
                "item_id": draft_id,
                "decision": "EDITED",
                "officer_name": officer_name,
                "notes": f"Konten diedit: {new_content[:80]}…",
            }
        )
        return jsonify({"status": "success", "message": f"Draft {draft_id} edited"})
    return jsonify({"status": "error", "message": "Failed to edit draft"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Coordination Plans (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/approval/plans")
@login_required
def api_get_plans():
    data = db.get_all_coordination_plans(limit=50)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/plans/pending")
@login_required
def api_get_pending_plans():
    data = db.get_all_pending_coordination_plans(limit=50)
    return jsonify({"status": "success", "count": len(data), "data": data})


@app.route("/api/approval/plan/<int:plan_id>/approve", methods=["POST"])
@login_required
def api_approve_plan(plan_id: int):
    body = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", session.get("operator", "Petugas BPBD"))

    plan = db.get_coordination_plan_by_id(plan_id)
    if plan is None:
        return jsonify({"status": "error", "message": "Plan not found"}), 404

    success = db.approve_coordination_plan(plan_id, officer_name)
    if success:
        db.insert_audit_log(
            {
                "action_type": "APPROVE",
                "item_table": "coordination_plans",
                "item_id": plan_id,
                "decision": "APPROVED",
                "officer_name": officer_name,
                "notes": body.get("notes", ""),
            }
        )
        return jsonify({"status": "success", "message": f"Plan {plan_id} approved"})
    return jsonify({"status": "error", "message": "Failed to approve plan"}), 500


@app.route("/api/approval/plan/<int:plan_id>/reject", methods=["POST"])
@login_required
def api_reject_plan(plan_id: int):
    body = request.get_json(silent=True) or {}
    officer_name = body.get("officer_name", session.get("operator", "Petugas BPBD"))
    notes = body.get("notes", "")

    plan = db.get_coordination_plan_by_id(plan_id)
    if plan is None:
        return jsonify({"status": "error", "message": "Plan not found"}), 404

    success = db.reject_coordination_plan(plan_id, officer_name)
    if success:
        db.insert_audit_log(
            {
                "action_type": "REJECT",
                "item_table": "coordination_plans",
                "item_id": plan_id,
                "decision": "REJECTED",
                "officer_name": officer_name,
                "notes": notes,
            }
        )
        return jsonify({"status": "success", "message": f"Plan {plan_id} rejected"})
    return jsonify({"status": "error", "message": "Failed to reject plan"}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — Audit Log (Fase 3)
# ─────────────────────────────────────────────────────────────
@app.route("/api/audit-log")
@login_required
def api_audit_log():
    limit = request.args.get("limit", 50, type=int)
    data = db.get_audit_log(limit=limit)
    return jsonify({"status": "success", "count": len(data), "data": data})


# ─────────────────────────────────────────────────────────────
#  REST API — Laporan per Gempa (T2.4)
# ─────────────────────────────────────────────────────────────
@app.route("/api/laporan/<int:eq_id>")
@login_required
def api_get_laporan(eq_id: int):
    """GET /api/laporan/<eq_id> — sitrep + drafts + coordination plan untuk satu gempa."""
    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Earthquake not found"}), 404

    sitrep = db.get_situation_report(eq_id)
    drafts = db.get_communication_drafts(eq_id)
    plan = db.get_coordination_plan(eq_id)

    return jsonify(
        {
            "status": "success",
            "data": {
                "earthquake": eq,
                "sitrep": sitrep,
                "drafts": drafts,
                "plan": plan,
            },
        }
    )



# ─────────────────────────────────────────────────────────────
#  REST API — Analytics (T3.6)
# ─────────────────────────────────────────────────────────────
@app.route("/api/analytics/monthly")
@login_required
def api_analytics_monthly():
    """GET /api/analytics/monthly — jumlah gempa per bulan dalam 12 bulan terakhir."""
    try:
        with db._connect() as conn:
            rows = conn.execute("""
                SELECT
                    strftime('%Y-%m', timestamp) AS month,
                    COUNT(*) AS total,
                    COUNT(CASE WHEN magnitude >= 5.0 THEN 1 END) AS major,
                    AVG(magnitude) AS avg_mag,
                    MAX(magnitude) AS max_mag
                FROM earthquakes
                WHERE timestamp >= datetime('now', '-12 months')
                GROUP BY month
                ORDER BY month ASC
            """).fetchall()
        data = [dict(r) for r in rows]
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        logger.error(f"Error analytics monthly: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/analytics/heatmap")
@login_required
def api_analytics_heatmap():
    """GET /api/analytics/heatmap — data lat/lon count untuk heatmap (grid 1°)."""
    try:
        with db._connect() as conn:
            rows = conn.execute("""
                SELECT
                    ROUND(latitude, 0)  AS lat_grid,
                    ROUND(longitude, 0) AS lon_grid,
                    COUNT(*) AS count,
                    MAX(magnitude) AS max_mag,
                    AVG(magnitude) AS avg_mag
                FROM earthquakes
                WHERE latitude IS NOT NULL AND longitude IS NOT NULL
                GROUP BY lat_grid, lon_grid
                ORDER BY count DESC
                LIMIT 200
            """).fetchall()
        data = [dict(r) for r in rows]
        return jsonify({"status": "success", "data": data})
    except Exception as e:
        logger.error(f"Error analytics heatmap: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/analytics/summary")
@login_required
def api_analytics_summary():
    """GET /api/analytics/summary — ringkasan statistik keseluruhan."""
    try:
        with db._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM earthquakes").fetchone()[0]
            major = conn.execute("SELECT COUNT(*) FROM earthquakes WHERE magnitude >= 5.0").fetchone()[0]
            avg_mag = conn.execute("SELECT AVG(magnitude) FROM earthquakes").fetchone()[0]
            max_mag = conn.execute("SELECT MAX(magnitude) FROM earthquakes").fetchone()[0]
            pipeline_done = conn.execute("SELECT COUNT(*) FROM earthquakes WHERE pipeline_status = 'DONE'").fetchone()[0]
            pending_pipeline = conn.execute("SELECT COUNT(*) FROM earthquakes WHERE pipeline_status = 'PENDING'").fetchone()[0]
            total_drafts = conn.execute("SELECT COUNT(*) FROM communication_drafts").fetchone()[0]
            approved_drafts = conn.execute("SELECT COUNT(*) FROM communication_drafts WHERE status = 'APPROVED'").fetchone()[0]
        return jsonify({
            "status": "success",
            "data": {
                "total_earthquakes": total,
                "major_earthquakes": major,
                "avg_magnitude": round(avg_mag, 2) if avg_mag else 0,
                "max_magnitude": round(max_mag, 2) if max_mag else 0,
                "pipeline_done": pipeline_done,
                "pipeline_pending": pending_pipeline,
                "pipeline_ratio": round(pipeline_done / max(total, 1) * 100, 1),
                "total_drafts": total_drafts,
                "approved_drafts": approved_drafts,
                "approval_ratio": round(approved_drafts / max(total_drafts, 1) * 100, 1),
            }
        })
    except Exception as e:
        logger.error(f"Error analytics summary: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─────────────────────────────────────────────────────────────
#  REST API — PDF Export (T3.5)
# ─────────────────────────────────────────────────────────────
def _generate_laporan_pdf_file(eq_id: int, operator_name: str) -> str:
    """Helper untuk men-generate PDF laporan gempa secara fisik dan mengembalikan path-nya."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.pdfgen import canvas
    import io

    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return None

    sitrep = db.get_situation_report(eq_id)
    drafts = db.get_communication_drafts(eq_id)
    plan = db.get_coordination_plan(eq_id)

    # Path physical untuk menyimpan laporan PDF secara lokal
    pdf_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "reports")
    os.makedirs(pdf_dir, exist_ok=True)
    pdf_path = os.path.join(pdf_dir, f"laporan_gempa_{eq_id}.pdf")

    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )

    styles = getSampleStyleSheet()
    RED = colors.HexColor("#F85149")
    DARK = colors.HexColor("#1c2128")
    GRAY = colors.HexColor("#7d8590")
    ORANGE = colors.HexColor("#D29922")

    h1 = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=18, textColor=RED, spaceAfter=4)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12, textColor=DARK, spaceAfter=6, spaceBefore=12)
    body = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, leading=14, textColor=DARK)
    label = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8, textColor=GRAY, spaceAfter=2)
    mono = ParagraphStyle("Mono", parent=styles["Code"], fontSize=9, leading=12, textColor=DARK)

    story = []

    # === HEADER ===
    story.append(Paragraph("CEPAT — Earthquake Report", h1))
    story.append(Paragraph(f"BPBD · Created: {datetime.now().strftime('%d %B %Y, %H:%M WIB')} · Operator: {operator_name}", label))
    story.append(HRFlowable(width="100%", thickness=1, color=RED, spaceAfter=12))

    # === DATA GEMPA ===
    story.append(Paragraph("Earthquake Data", h2))
    eq_data = [
        ["Magnitude", f"M {float(eq.get('magnitude', 0)):.1f}"],
        ["Location", eq.get("location_desc", "—")],
        ["Depth", f"{eq.get('depth_km', '—')} km"],
        ["Coordinates", f"{eq.get('latitude', '—')}°, {eq.get('longitude', '—')}°"],
        ["Time", eq.get("timestamp", "—")],
        ["Tsunami Potential", eq.get("tsunami_potential", "None")],
    ]
    t = Table(eq_data, colWidths=[4*cm, 13*cm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
        ("PADDING", (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f6f8fa"), colors.white]),
    ]))
    story.append(t)

    # === SITUATION REPORT ===
    if sitrep:
        story.append(Paragraph("Situation Report", h2))
        story.append(Paragraph(f"Risk Level: <b>{sitrep.get('risk_level', '—')}</b>", body))
        story.append(Spacer(1, 6))
        if sitrep.get("summary"):
            story.append(Paragraph("Summary:", label))
            story.append(Paragraph(sitrep["summary"], body))
        if sitrep.get("affected_areas"):
            story.append(Spacer(1, 6))
            story.append(Paragraph("Affected Areas:", label))
            story.append(Paragraph(sitrep["affected_areas"], body))
        recs = sitrep.get("recommendations", [])
        if recs:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Recommendations:", label))
            for i, r in enumerate(recs, 1):
                story.append(Paragraph(f"{i}. {r}", body))

    # === DRAF KOMUNIKASI ===
    if drafts:
        story.append(Paragraph("Communication Drafts", h2))
        DRAFT_NAMES = {
            "public_id": "Bahasa Indonesia",
            "public_minang": "Bahasa Minang",
            "technical": "Teknis/Formal",
            "english": "English",
        }
        for d in drafts:
            name = DRAFT_NAMES.get(d.get("draft_type", ""), d.get("draft_type", "DRAFT"))
            status_txt = d.get("status", "DRAFT")
            story.append(Paragraph(f"<b>{name}</b> <font color='#7d8590'>[{status_txt}]</font>", body))
            story.append(Paragraph(d.get("content", "—"), mono))
            story.append(Spacer(1, 6))

    # === RENCANA KOORDINASI ===
    if plan:
        story.append(Paragraph("Coordination Plan", h2))
        if plan.get("resource_mapping"):
            story.append(Paragraph("Resource Mapping:", label))
            story.append(Paragraph(plan["resource_mapping"], body))
        priorities = plan.get("action_priorities", [])
        if priorities:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Priority Actions:", label))
            prio_data = [["Priority", "Action", "Time"]]
            for ap in priorities:
                prio = ap.get("priority") or ap.get("level", "—")
                action_txt = ap.get("action") or ap.get("description", str(ap))
                timeline = ap.get("timeline") or ap.get("time", "—")
                prio_data.append([prio, action_txt, timeline])
            pt = Table(prio_data, colWidths=[2.5*cm, 11*cm, 3.5*cm])
            pt.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1c2128")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d0d7de")),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f6f8fa"), colors.white]),
            ]))
            story.append(pt)

    # === FOOTER ===
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=GRAY))
    story.append(Paragraph(f"This document was automatically generated by CEPAT · Operator: {operator_name} · {datetime.now().strftime('%d/%m/%Y %H:%M')}", label))

    doc.build(story)
    return pdf_path


DOWNLOAD_TOKENS = {}  # token -> (eq_id, expires_at)


@app.route("/api/laporan/<int:eq_id>/pdf-token", methods=["POST"])
@login_required
def api_laporan_pdf_token(eq_id: int):
    """POST /api/laporan/<eq_id>/pdf-token — Generate token unduhan PDF sekali pakai (secure)."""
    import secrets
    import time

    eq = db.get_earthquake_by_id(eq_id)
    if eq is None:
        return jsonify({"status": "error", "message": "Earthquake not found"}), 404

    token = secrets.token_urlsafe(16)
    DOWNLOAD_TOKENS[token] = (eq_id, time.time() + 60)  # valid 60 detik
    return jsonify({"status": "success", "token": token})


@app.route("/api/laporan/download/pdf")
def api_laporan_pdf_download_public():
    """GET /api/laporan/download/pdf?token=xxx — Unduh PDF menggunakan token sekali pakai (tanpa session cookie block)."""
    import time
    from flask import send_file

    token = request.args.get("token")
    if not token or token not in DOWNLOAD_TOKENS:
        return "Token unduhan tidak valid atau sudah digunakan.", 403

    eq_id, expires_at = DOWNLOAD_TOKENS[token]
    # Hapus token setelah digunakan (single-use)
    del DOWNLOAD_TOKENS[token]

    if time.time() > expires_at:
        return "Token unduhan sudah kedaluwarsa.", 403

    try:
        operator_name = "Sistem CEPAT"
        pdf_path = _generate_laporan_pdf_file(eq_id, operator_name)
        if not pdf_path:
            return "Gempa tidak ditemukan.", 404

        filename = f"laporan_gempa_{eq_id}.pdf"
        return send_file(pdf_path, as_attachment=True, download_name=filename, mimetype="application/pdf")
    except Exception as e:
        logger.error(f"Gagal generate PDF via token: {e}")
        return "Internal server error saat men-generate PDF.", 500


@app.route("/api/laporan/<int:eq_id>/pdf")
@login_required
def api_laporan_pdf(eq_id: int):
    """GET /api/laporan/<eq_id>/pdf — generate dan download PDF laporan gempa (legacy)."""
    from flask import send_file
    try:
        operator_name = session.get("operator", "Operator BPBD")
        pdf_path = _generate_laporan_pdf_file(eq_id, operator_name)
        if not pdf_path:
            return jsonify({"status": "error", "message": "Earthquake not found"}), 404

        filename = f"laporan_gempa_{eq_id}.pdf"
        return send_file(pdf_path, as_attachment=True, download_name=filename, mimetype="application/pdf")
    except ImportError:
        return jsonify({"status": "error", "message": "reportlab is not installed."}), 500
    except Exception as e:
        logger.error(f"Gagal generate PDF: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500



# ─────────────────────────────────────────────────────────────
#  REST API — Admin User Management (T3.4)
# ─────────────────────────────────────────────────────────────
def admin_required(f):
    """Decorator: hanya admin yang bisa akses."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("operator"):
            return jsonify({"status": "error", "message": "Login required"}), 401
        if session.get("role") != "admin":
            return jsonify({"status": "error", "message": "Akses admin diperlukan"}), 403
        return f(*args, **kwargs)
    return decorated


@app.route("/api/admin/operators")
@login_required
def api_admin_list_operators():
    """GET /api/admin/operators — list semua operator (admin: semua, operator: only self)."""
    ops = db.get_all_operators()
    if session.get("role") != "admin":
        # Non-admin can only see their own info
        ops = [o for o in ops if o["username"] == session.get("operator")]
    return jsonify({"status": "success", "data": ops})


@app.route("/api/admin/operators", methods=["POST"])
@login_required
def api_admin_create_operator():
    """POST /api/admin/operators — buat operator baru (admin only)."""
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Akses admin diperlukan"}), 403
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    full_name = data.get("full_name", username)
    role = data.get("role", "operator")
    if not username or not password:
        return jsonify({"status": "error", "message": "Username dan password wajib diisi"}), 400
    result = db.create_operator(username, password, full_name, role)
    if result.get("success"):
        return jsonify({"status": "success", "message": f"Operator '{username}' successfully created"})
    return jsonify({"status": "error", "message": result.get("error", "Failed to create operator")}), 400


@app.route("/api/admin/operators/<int:op_id>/toggle", methods=["POST"])
@login_required
def api_admin_toggle_operator(op_id: int):
    """POST /api/admin/operators/<id>/toggle — aktifkan/nonaktifkan operator (admin only)."""
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Akses admin diperlukan"}), 403
    result = db.toggle_operator(op_id)
    if result.get("success"):
        status = "active" if result["is_active"] else "inactive"
        return jsonify({"status": "success", "message": f"Operator is now {status}", "is_active": result["is_active"]})
    return jsonify({"status": "error", "message": result.get("error", "Gagal toggle")}), 400


@app.route("/api/admin/operators/<int:op_id>/reset-password", methods=["POST"])
@login_required
def api_admin_reset_password(op_id: int):
    """POST /api/admin/operators/<id>/reset-password — reset password (admin only)."""
    if session.get("role") != "admin":
        return jsonify({"status": "error", "message": "Akses admin diperlukan"}), 403
    data = request.get_json() or {}
    new_password = data.get("password", "")
    if not new_password or len(new_password) < 6:
        return jsonify({"status": "error", "message": "Password must be at least 6 characters"}), 400
    result = db.reset_operator_password(op_id, new_password)
    if result.get("success"):
        return jsonify({"status": "success", "message": "Password reset successfully"})
    return jsonify({"status": "error", "message": result.get("error", "Failed to reset password")}), 400


@app.route("/api/me")
@login_required
def api_me():
    """GET /api/me — info operator yang sedang login."""
    op = db.get_operator_by_username(session.get("operator", ""))
    return jsonify({
        "operator": session.get("operator"),
        "role": session.get("role", "operator"),
        "full_name": session.get("full_name", session.get("operator")),
        "last_login": op.get("last_login") if op else None,
    })


# ─────────────────────────────────────────────────────────────
#  Error Handlers
# ─────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Endpoint not found"}), 404


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

    # Hanya jalankan orchestrator di proses utama (mencegah double-thread saat reload)
    if not FLASK_DEBUG or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        orchestrator.start()

    logger.info(f"Dashboard berjalan di http://{FLASK_HOST}:{FLASK_PORT}")
    socketio.run(
        app,
        host=FLASK_HOST,
        port=FLASK_PORT,
        debug=FLASK_DEBUG,
        use_reloader=FLASK_DEBUG,
        allow_unsafe_werkzeug=True,
    )
