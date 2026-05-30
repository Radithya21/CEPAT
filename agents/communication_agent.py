"""
communication_agent.py — CEPAT Communication Agent (Fase 3)
Menghasilkan 3 versi draf pesan alert dari Situation Report:
  - public_id    : Bahasa Indonesia, maks 160 karakter
  - public_minang: Bahasa Minang untuk komunitas Sumatera Barat
  - technical    : Laporan teknis formal antar-instansi
"""

import sys
import os
import re
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import GEMINI_API_KEY, GEMINI_COMM_MODEL
from database.db_handler import DatabaseHandler

logger = logging.getLogger("CommunicationAgent")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


_RISK_LABELS = {
    "CRITICAL": "KRITIS",
    "HIGH":     "TINGGI",
    "MEDIUM":   "SEDANG",
    "LOW":      "RENDAH",
}


class CommunicationAgent:
    """
    Agent yang membuat draf pesan alert berdasarkan Situation Report.

    Cara pakai:
        agent = CommunicationAgent()
        drafts = agent.run(earthquake_id)   # return list[dict]
    """

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db = db_handler or DatabaseHandler()
        self._model = None
        self._prompt_template = _load_prompt("communication_alert.txt")

        if GEMINI_API_KEY:
            try:
                from google import genai
                self._model = genai.Client(api_key=GEMINI_API_KEY)
                logger.info("Gemini client (communication) diinisialisasi.")
            except ImportError:
                logger.warning("Package 'google-genai' tidak ditemukan. Jalankan: pip install google-genai")
        else:
            logger.warning("GEMINI_API_KEY tidak diset — akan menggunakan fallback drafts.")

    # ─────────────────────────────────────────────────────────
    #  Format Sitrep untuk Prompt
    # ─────────────────────────────────────────────────────────

    def _format_sitrep(self, sitrep: dict) -> str:
        recs = sitrep.get("recommendations", [])
        if isinstance(recs, str):
            try:
                recs = json.loads(recs)
            except Exception:
                recs = [recs]
        recs_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(recs)) if recs else "  —"
        risk_label = _RISK_LABELS.get(sitrep.get("risk_level", "MEDIUM"), sitrep.get("risk_level", "—"))
        return (
            f"Lokasi         : {sitrep.get('location_desc', '—')}\n"
            f"Waktu          : {sitrep.get('eq_timestamp', '—')}\n"
            f"Magnitudo      : M{sitrep.get('magnitude', '—')} SR\n"
            f"Level Risiko   : {risk_label} ({sitrep.get('risk_level', '—')})\n"
            f"Ringkasan      : {sitrep.get('summary', '—')}\n"
            f"Wilayah Terdampak: {sitrep.get('affected_areas', '—')}\n"
            f"Rekomendasi    :\n{recs_text}"
        )

    # ─────────────────────────────────────────────────────────
    #  LLM Draft Generation
    # ─────────────────────────────────────────────────────────

    def _generate_llm_drafts(self, sitrep: dict) -> dict | None:
        if not self._model:
            return None

        sitrep_text = self._format_sitrep(sitrep)

        try:
            prompt = self._prompt_template.format(situation_report=sitrep_text)
        except KeyError as e:
            logger.error(f"Template communication_alert.txt error: {e}")
            return None

        try:
            response = self._model.models.generate_content(
                model=GEMINI_COMM_MODEL,
                contents=prompt,
                config={"max_output_tokens": 1200},
            )
            if not response.text:
                logger.warning("Respons Gemini diblokir safety filter.")
                return None
            raw = response.text.strip()

            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not json_match:
                logger.warning("Respons Gemini tidak mengandung JSON.")
                return None

            result = json.loads(json_match.group())
            return {
                "public_id":     str(result.get("public_id", ""))[:200],
                "public_minang": str(result.get("public_minang", "")),
                "technical":     str(result.get("technical", "")),
                "english":       str(result.get("english", ""))[:200],
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Gagal parse JSON dari Gemini: {e}")
        except Exception as e:
            logger.error(f"Error Gemini communication: {e}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Fallback Drafts
    # ─────────────────────────────────────────────────────────

    def _generate_fallback_drafts(self, sitrep: dict) -> dict:
        mag  = sitrep.get("magnitude", 0)
        loc  = sitrep.get("location_desc", "wilayah terdampak")
        risk = sitrep.get("risk_level", "MEDIUM")
        ts   = sitrep.get("eq_timestamp", "")

        # Alert publik — maks 160 karakter
        public_id = f"GEMPA M{mag} {loc}. Risiko {_RISK_LABELS.get(risk, risk)}. Ikuti arahan BPBD. Jauhi bangunan rusak."
        public_id = public_id[:160]

        # Bahasa Minang
        public_minang = (
            f"GEMPA BUMI M{mag} di {loc}. "
            f"Ikolah imbauan BPBD, jauahi bangunan nan rusak, jan panik. "
            f"Tingkek risiko: {_RISK_LABELS.get(risk, risk)}."
        )

        # Laporan teknis
        technical = (
            f"LAPORAN TEKNIS — BPBD\n"
            f"Gempa: M{mag} SR | Lokasi: {loc}\n"
            f"Waktu: {ts}\n"
            f"Level Risiko: {risk}\n"
            f"Ringkasan: {sitrep.get('summary', '—')}\n"
            f"Wilayah Terdampak: {sitrep.get('affected_areas', '—')}\n"
            f"Status: Monitoring aktif. Koordinasi segera diperlukan."
        )

        # English public alert
        risk_en = {"CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "MODERATE", "LOW": "LOW"}.get(risk, risk)
        english = f"EARTHQUAKE M{mag} {loc}. Risk: {risk_en}. Follow local authority instructions. Avoid damaged structures."
        english = english[:200]

        return {"public_id": public_id, "public_minang": public_minang, "technical": technical, "english": english}

    # ─────────────────────────────────────────────────────────
    #  Main Run
    # ─────────────────────────────────────────────────────────

    def run(self, earthquake_id: int) -> list[dict]:
        """
        Buat 3 draf pesan untuk satu gempa.
        Return list draf yang berhasil disimpan ke DB.
        """
        sitrep = self.db.get_situation_report(earthquake_id)
        if not sitrep:
            logger.warning(f"Tidak ada sitrep untuk gempa {earthquake_id} — lewati Communication Agent.")
            return []

        logger.info(f"CommunicationAgent: membuat draf untuk gempa ID={earthquake_id} M{sitrep.get('magnitude')}")

        drafts_data = self._generate_llm_drafts(sitrep)
        if drafts_data is None:
            logger.warning("LLM gagal/tidak tersedia — menggunakan fallback drafts.")
            drafts_data = self._generate_fallback_drafts(sitrep)

        draft_types = [
            ("public_id",     drafts_data.get("public_id", "")),
            ("public_minang", drafts_data.get("public_minang", "")),
            ("technical",     drafts_data.get("technical", "")),
            ("english",       drafts_data.get("english", "")),
        ]

        saved = []
        for dtype, content in draft_types:
            if not content.strip():
                continue
            draft = {
                "situation_report_id": sitrep["id"],
                "earthquake_id":       earthquake_id,
                "draft_type":          dtype,
                "content":             content,
            }
            draft_id = self.db.insert_communication_draft(draft)
            if draft_id:
                draft["id"] = draft_id
                saved.append(draft)
                logger.info(f"  Draf [{dtype}] tersimpan (ID={draft_id})")

        logger.info(f"CommunicationAgent selesai: {len(saved)}/4 draf disimpan untuk gempa {earthquake_id}")
        return saved


# ─────────────────────────────────────────────────────────────
#  Test standalone
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s")
    agent = CommunicationAgent()
    from database.db_handler import DatabaseHandler
    db = DatabaseHandler()
    sitreps = db.get_all_situation_reports(limit=1)
    if sitreps:
        eq_id = sitreps[0]["earthquake_id"]
        drafts = agent.run(eq_id)
        print(f"\nDibuat {len(drafts)} draf untuk gempa {eq_id}")
        for d in drafts:
            print(f"  [{d['draft_type']}] {d['content'][:80]}…")
    else:
        print("Tidak ada sitrep di database.")
