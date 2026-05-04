"""
analysis_agent.py — CEPAT Analysis Agent (Fase 2)
Mensintesis data gempa + intelligence reports menjadi
Situation Report yang actionable menggunakan Claude API.
Jika API tidak tersedia, fallback ke rule-based report.
"""

import sys
import os
import re
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GEMINI_API_KEY, GEMINI_ANALYSIS_MODEL, GEMINI_MAX_TOKENS,
)
from database.db_handler import DatabaseHandler

logger = logging.getLogger("AnalysisAgent")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Risk level berdasarkan magnitudo (untuk fallback)
_RISK_RULES = [
    (7.0, "CRITICAL"),
    (6.0, "HIGH"),
    (5.0, "MEDIUM"),
    (0.0, "LOW"),
]

_FALLBACK_RECS = {
    "CRITICAL": [
        "Segera aktifkan Status Siaga I dan Pusat Komando Darurat",
        "Evakuasi warga zona merah tsunami ke tempat aman",
        "Koordinasi dengan TNI/Polri dan BASARNAS untuk bantuan darurat",
        "Buka posko pengungsian di lokasi yang sudah ditetapkan",
        "Kirim tim SAR ke area terdampak dan laporkan kondisi lapangan",
    ],
    "HIGH": [
        "Aktifkan Status Siaga II dan persiapkan tim respons lapangan",
        "Pantau potensi tsunami dan gempa susulan secara intensif",
        "Lakukan koordinasi lintas SKPD dan lembaga terkait",
        "Siapkan inventaris logistik bantuan darurat",
        "Lakukan pendataan awal kerusakan infrastruktur dan korban",
    ],
    "MEDIUM": [
        "Aktifkan Status Waspada dan standby tim BPBD",
        "Pantau perkembangan situasi dan laporan lapangan",
        "Koordinasi dengan BMKG untuk pemantauan aftershock",
        "Siapkan tim reaksi cepat jika situasi memburuk",
    ],
    "LOW": [
        "Pantau perkembangan situasi",
        "Standby tim BPBD dan pastikan komunikasi berjalan",
        "Informasikan masyarakat agar tidak panik",
    ],
}


class AnalysisAgent:
    """
    Agent analisis yang menghasilkan Situation Report.

    Cara pakai:
        agent = AnalysisAgent()
        report = agent.run(earthquake_id)   # return dict atau None
    """

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db = db_handler or DatabaseHandler()
        self._model = None
        self._sitrep_prompt_template = _load_prompt("situation_report.txt")

        if GEMINI_API_KEY:
            try:
                from google import genai
                self._model = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini client (analysis) diinisialisasi.")
            except ImportError:
                logger.warning("Package 'google-genai' tidak ditemukan. Jalankan: pip install google-genai")
        else:
            logger.warning("GEMINI_API_KEY tidak diset — akan menggunakan fallback rule-based report.")

    # ─────────────────────────────────────────────────────────
    #  Formatting Input
    # ─────────────────────────────────────────────────────────

    def _format_earthquake(self, eq: dict) -> str:
        def ts(t):
            if not t:
                return "—"
            try:
                from datetime import datetime
                d = datetime.fromisoformat(t)
                return d.strftime("%d %b %Y %H:%M WIB")
            except Exception:
                return t

        tsunami = eq.get("tsunami_potential", "")
        felt    = eq.get("felt_area", "")
        return (
            f"Magnitudo     : {eq.get('magnitude')} SR\n"
            f"Lokasi        : {eq.get('location_desc')}\n"
            f"Kedalaman     : {eq.get('depth_km')} km\n"
            f"Waktu         : {ts(eq.get('timestamp'))}\n"
            f"Koordinat     : {eq.get('latitude')}, {eq.get('longitude')}\n"
            f"Potensi Tsunami: {tsunami or 'Tidak ada informasi'}\n"
            f"Dirasakan     : {felt or 'Tidak ada laporan'}"
        )

    def _format_intel(self, intel_reports: list[dict]) -> str:
        if not intel_reports:
            return "Belum ada laporan dari media/lapangan."
        lines = []
        for r in intel_reports:
            icon = {"VALID": "✔", "HOAX": "✘", "UNVERIFIED": "?"}.get(r.get("credibility_status"), "?")
            lines.append(
                f"[{icon} {r.get('credibility_status','?')}] "
                f"{r.get('source_name','')} — {r.get('title','')}"
            )
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    #  LLM Report
    # ─────────────────────────────────────────────────────────

    def _generate_llm_report(self, eq: dict, intel: list[dict]) -> dict | None:
        """Hasilkan Situation Report menggunakan Gemini. Return dict atau None jika gagal."""
        if not self._model:
            return None

        try:
            prompt = self._sitrep_prompt_template.format(
                earthquake_data=self._format_earthquake(eq),
                intelligence_data=self._format_intel(intel),
            )
        except KeyError as e:
            logger.error(f"Template situation_report.txt error — placeholder tidak valid: {e}")
            return None

        try:
            response = self._model.models.generate_content(
                model=GEMINI_ANALYSIS_MODEL,
                contents=prompt,
                config={"max_output_tokens": GEMINI_MAX_TOKENS},
            )
            if not response.text:
                logger.warning("Respons Gemini diblokir safety filter.")
                return None
            raw_text = response.text.strip()

            # Extract JSON — bisa ada teks sebelum/sesudah JSON
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if not json_match:
                logger.warning("Respons Gemini tidak mengandung JSON.")
                return None

            result = json.loads(json_match.group())

            # Validasi field wajib
            risk = result.get("risk_level", "MEDIUM").upper()
            if risk not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
                risk = "MEDIUM"

            recs = result.get("recommendations", [])
            if isinstance(recs, str):
                recs = [recs]

            return {
                "summary":            result.get("summary", ""),
                "affected_areas":     result.get("affected_areas", ""),
                "risk_level":         risk,
                "risk_justification": result.get("risk_justification", ""),
                "recommendations":    recs,
                "notes":              result.get("notes", ""),
                "raw_llm_output":     raw_text,
                "generated_by":       "llm",
            }

        except json.JSONDecodeError as e:
            logger.warning(f"Gagal parse JSON dari Gemini: {e}")
        except Exception as e:
            logger.error(f"Error Gemini analysis: {e}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Fallback Rule-based Report
    # ─────────────────────────────────────────────────────────

    def _generate_fallback_report(self, eq: dict) -> dict:
        """Hasilkan Situation Report berbasis aturan (tanpa LLM)."""
        mag = eq.get("magnitude", 0)

        # Tentukan risk level
        risk = "LOW"
        for threshold, level in _RISK_RULES:
            if mag >= threshold:
                risk = level
                break

        tsunami_text = eq.get("tsunami_potential", "")
        is_tsunami   = "berpotensi" in tsunami_text.lower() and "tidak" not in tsunami_text.lower()

        summary = (
            f"Gempa berkekuatan M{mag} mengguncang wilayah {eq.get('location_desc')} "
            f"pada kedalaman {eq.get('depth_km')} km. "
            f"{'⚠ BERPOTENSI TSUNAMI — warga pesisir harap menjauh dari pantai.' if is_tsunami else 'Tidak berpotensi tsunami.'} "
            f"Gempa dirasakan di: {eq.get('felt_area') or 'belum ada laporan'}."
        )

        return {
            "summary":            summary,
            "affected_areas":     eq.get("location_desc", ""),
            "risk_level":         risk,
            "risk_justification": (
                f"Magnitudo {mag} SR dengan kedalaman {eq.get('depth_km')} km. "
                f"{'Potensi tsunami terdeteksi.' if is_tsunami else 'Tidak berpotensi tsunami.'}"
            ),
            "recommendations":    _FALLBACK_RECS.get(risk, _FALLBACK_RECS["LOW"]),
            "notes":              "Laporan ini dibuat secara otomatis (rule-based) — harap verifikasi manual.",
            "raw_llm_output":     "",
            "generated_by":       "fallback",
        }

    # ─────────────────────────────────────────────────────────
    #  Main Run
    # ─────────────────────────────────────────────────────────

    def run(self, earthquake_id: int) -> dict | None:
        """
        Hasilkan Situation Report untuk satu gempa.
        1. Ambil data gempa + intelligence reports dari DB
        2. Coba LLM → fallback jika gagal
        3. Simpan ke DB
        Return dict Situation Report atau None jika error.
        """
        eq = self.db.get_earthquake_by_id(earthquake_id)
        if not eq:
            logger.error(f"Gempa ID {earthquake_id} tidak ditemukan.")
            return None

        intel = self.db.get_intelligence_reports(earthquake_id)
        logger.info(
            f"AnalysisAgent: membuat Sitrep untuk gempa ID={earthquake_id} "
            f"M{eq['magnitude']} ({len(intel)} intel reports)"
        )

        # Coba LLM dulu
        report_data = self._generate_llm_report(eq, intel)

        # Fallback jika LLM gagal
        if report_data is None:
            logger.warning("LLM gagal/tidak tersedia — menggunakan fallback rule-based report.")
            report_data = self._generate_fallback_report(eq)

        # Tambahkan earthquake_id dan simpan
        report_data["earthquake_id"] = earthquake_id
        success = self.db.insert_situation_report(report_data)

        if success:
            gen_by = report_data.get("generated_by", "?")
            risk   = report_data.get("risk_level", "?")
            logger.info(
                f"Sitrep disimpan: gempa {earthquake_id} | "
                f"risk={risk} | generated_by={gen_by}"
            )
            return report_data

        logger.error(f"Gagal menyimpan Sitrep untuk gempa {earthquake_id}")
        return None
