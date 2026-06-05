"""
coordination_agent.py — CEPAT Coordination Agent (Fase 3)
Membuat rencana koordinasi lapangan berdasarkan Situation Report:
  - Mapping kebutuhan vs ketersediaan sumber daya
  - 5 aksi prioritas (P1/P2/P3) dengan estimasi timeline
"""

import sys
import os
import re
import json
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_handler import DatabaseHandler
from utils.llm_client import LLMClient

logger = logging.getLogger("CoordinationAgent")

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts")


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Sumber daya standar BPBD (untuk demo / hardcoded)
DEFAULT_RESOURCES = {
    "Personel": {
        "Tim SAR": 2,
        "Petugas BPBD": 15,
        "Relawan terlatih": 30,
        "Tenaga medis (dokter/perawat)": 8,
    },
    "Logistik": {
        "Paket sembako": 500,
        "Tenda pengungsi kapasitas 10 orang": 20,
        "Selimut / matras": 200,
        "Obat-obatan dasar": "1 kontainer",
        "Air bersih (liter)": 10000,
    },
    "Peralatan & Kendaraan": {
        "Excavator": 1,
        "Ambulans": 3,
        "Mobil rescue BPBD": 2,
        "Perahu karet": 4,
        "Genset portable": 5,
        "Drone pemetaan": 1,
    },
}

_FALLBACK_ACTIONS = {
    "CRITICAL": [
        {"priority": "P1", "action": "Aktivasi Posko Darurat",
         "description": "Aktifkan Pusat Komando Darurat, tetapkan Status Siaga I, koordinasikan dengan BNPB dan TNI/Polri.", "timeline_hours": 1},
        {"priority": "P1", "action": "Evakuasi Zona Merah",
         "description": "Evakuasi paksa warga di zona risiko tinggi: pesisir, lereng curam, dan bangunan rusak berat.", "timeline_hours": 2},
        {"priority": "P2", "action": "Penilaian Kerusakan & Korban",
         "description": "Kerahkan tim SAR dan medis untuk asesmen cepat jumlah korban, kerusakan infrastruktur, dan kebutuhan mendesak.", "timeline_hours": 4},
        {"priority": "P2", "action": "Distribusi Logistik Darurat",
         "description": "Distribusikan paket sembako, air bersih, tenda, dan obat-obatan ke posko pengungsian.", "timeline_hours": 6},
        {"priority": "P3", "action": "Pemulihan Infrastruktur Kritis",
         "description": "Prioritaskan perbaikan akses jalan utama, jaringan listrik, dan fasilitas kesehatan.", "timeline_hours": 24},
    ],
    "HIGH": [
        {"priority": "P1", "action": "Aktivasi Tim Respons",
         "description": "Aktifkan Status Siaga II, kerahkan tim BPBD dan koordinasi dengan instansi terkait.", "timeline_hours": 1},
        {"priority": "P1", "action": "Asesmen Lapangan Cepat",
         "description": "Kerahkan tim SAR untuk penilaian awal kerusakan dan identifikasi korban di daerah terdampak.", "timeline_hours": 2},
        {"priority": "P2", "action": "Pendirikan Posko Pengungsi",
         "description": "Dirikan tenda pengungsian, siapkan logistik dasar, dan pastikan ketersediaan air bersih.", "timeline_hours": 4},
        {"priority": "P2", "action": "Koordinasi Medis",
         "description": "Aktifkan pos medis lapangan, koordinasi rumah sakit terdekat untuk penanganan korban luka.", "timeline_hours": 6},
        {"priority": "P3", "action": "Pendataan & Pemulihan",
         "description": "Lakukan pendataan warga terdampak, distribusi bantuan lanjutan, mulai pemulihan infrastruktur.", "timeline_hours": 12},
    ],
    "MEDIUM": [
        {"priority": "P1", "action": "Aktivasi Kesiapsiagaan",
         "description": "Aktifkan Status Waspada, standby tim BPBD, dan pantau perkembangan situasi.", "timeline_hours": 1},
        {"priority": "P1", "action": "Pemantauan Gempa Susulan",
         "description": "Koordinasi dengan BMKG untuk pemantauan gempa susulan dan potensi bahaya sekunder.", "timeline_hours": 2},
        {"priority": "P2", "action": "Verifikasi Lapangan",
         "description": "Kirim tim untuk verifikasi kondisi lapangan, kerusakan bangunan, dan kebutuhan bantuan.", "timeline_hours": 4},
        {"priority": "P2", "action": "Komunikasi Publik",
         "description": "Sebarkan informasi resmi melalui media dan media sosial untuk mencegah kepanikan.", "timeline_hours": 4},
        {"priority": "P3", "action": "Dukungan Psikososial",
         "description": "Siapkan layanan konseling dan dukungan psikososial untuk warga terdampak.", "timeline_hours": 12},
    ],
    "LOW": [
        {"priority": "P1", "action": "Monitoring Situasi",
         "description": "Pantau perkembangan situasi secara berkala dan koordinasikan dengan BMKG.", "timeline_hours": 1},
        {"priority": "P2", "action": "Informasi Publik",
         "description": "Sampaikan informasi resmi agar masyarakat tidak panik dan tetap waspada.", "timeline_hours": 2},
        {"priority": "P2", "action": "Standby Tim BPBD",
         "description": "Pastikan tim BPBD dalam kondisi siap dan komunikasi berjalan lancar.", "timeline_hours": 3},
        {"priority": "P3", "action": "Koordinasi Pemantauan",
         "description": "Koordinasi dengan instansi terkait untuk pemantauan lingkungan pasca gempa.", "timeline_hours": 6},
        {"priority": "P3", "action": "Evaluasi Kesiapsiagaan",
         "description": "Lakukan evaluasi kesiapsiagaan dan pastikan semua SOP respons bencana siap diaktifkan.", "timeline_hours": 12},
    ],
}


class CoordinationAgent:
    """
    Agent koordinasi lapangan BPBD.

    Cara pakai:
        agent = CoordinationAgent()
        plan = agent.run(earthquake_id)   # return dict atau None
    """

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db = db_handler or DatabaseHandler()
        self._llm = LLMClient()
        self._prompt_template = _load_prompt("coordination_plan.txt")
        logger.info("CoordinationAgent siap — menggunakan LLMClient (Groq → Ollama → Fallback).")

    # ─────────────────────────────────────────────────────────
    #  Format Inputs
    # ─────────────────────────────────────────────────────────

    def _format_sitrep(self, sitrep: dict) -> str:
        recs = sitrep.get("recommendations", [])
        if isinstance(recs, str):
            try:
                recs = json.loads(recs)
            except Exception:
                recs = [recs]
        recs_text = "\n".join(f"  {i+1}. {r}" for i, r in enumerate(recs)) if recs else "  —"
        return (
            f"Lokasi         : {sitrep.get('location_desc', '—')}\n"
            f"Waktu          : {sitrep.get('eq_timestamp', '—')}\n"
            f"Magnitudo      : M{sitrep.get('magnitude', '—')} SR\n"
            f"Level Risiko   : {sitrep.get('risk_level', '—')}\n"
            f"Ringkasan      : {sitrep.get('summary', '—')}\n"
            f"Wilayah Terdampak: {sitrep.get('affected_areas', '—')}\n"
            f"Rekomendasi    :\n{recs_text}"
        )

    def _format_resources(self) -> str:
        lines = []
        for category, items in DEFAULT_RESOURCES.items():
            lines.append(f"{category}:")
            for item, qty in items.items():
                lines.append(f"  - {item}: {qty}")
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    #  LLM Plan Generation
    # ─────────────────────────────────────────────────────────

    def _generate_llm_plan(self, sitrep: dict) -> dict | None:
        try:
            prompt = self._prompt_template.format(
                situation_report=self._format_sitrep(sitrep),
                resources=self._format_resources(),
            )
        except KeyError as e:
            logger.error(f"Template coordination_plan.txt error: {e}")
            return None

        raw = self._llm.generate(prompt, max_tokens=2000)
        if not raw:
            return None

        try:
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not json_match:
                logger.warning("Respons LLM tidak mengandung JSON.")
                return None

            result = json.loads(json_match.group())

            priorities = result.get("action_priorities", [])
            if not isinstance(priorities, list):
                priorities = []

            return {
                "resource_mapping":   str(result.get("resource_mapping", "")),
                "action_priorities":  priorities[:5],
                "estimated_timeline": str(result.get("estimated_timeline", "")),
                "generated_by":       f"llm:{self._llm.last_provider}",
            }
        except json.JSONDecodeError as e:
            logger.warning(f"Gagal parse JSON dari LLM: {e}")
        except Exception as e:
            logger.error(f"Error coordination LLM: {e}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Fallback Plan
    # ─────────────────────────────────────────────────────────

    def _generate_fallback_plan(self, sitrep: dict) -> dict:
        risk = sitrep.get("risk_level", "MEDIUM")
        mag  = sitrep.get("magnitude", 0)
        loc  = sitrep.get("location_desc", "—")

        resource_mapping = (
            f"Gempa M{mag} di {loc} membutuhkan mobilisasi sumber daya segera.\n"
            f"Personel: Kerahkan tim SAR (prioritas), petugas BPBD, dan relawan terlatih.\n"
            f"Logistik: Siapkan paket sembako dan tenda untuk pengungsian, air bersih segera didistribusikan.\n"
            f"Peralatan: Excavator dan ambulans disiagakan. Genset untuk backup listrik posko darurat."
        )

        actions = _FALLBACK_ACTIONS.get(risk, _FALLBACK_ACTIONS["MEDIUM"])

        timeline_map = {"CRITICAL": "72 jam intensif", "HIGH": "48 jam intensif", "MEDIUM": "24 jam monitoring", "LOW": "12 jam pantau"}

        return {
            "resource_mapping":   resource_mapping,
            "action_priorities":  actions,
            "estimated_timeline": timeline_map.get(risk, "24 jam"),
            "generated_by":       "fallback",
        }

    # ─────────────────────────────────────────────────────────
    #  Main Run
    # ─────────────────────────────────────────────────────────

    def run(self, earthquake_id: int) -> dict | None:
        """
        Buat rencana koordinasi untuk satu gempa.
        Return dict plan atau None jika gagal.
        """
        sitrep = self.db.get_situation_report(earthquake_id)
        if not sitrep:
            logger.warning(f"Tidak ada sitrep untuk gempa {earthquake_id} — lewati Coordination Agent.")
            return None

        logger.info(f"CoordinationAgent: membuat plan untuk gempa ID={earthquake_id} M{sitrep.get('magnitude')}")

        plan_data = self._generate_llm_plan(sitrep)
        if plan_data is None:
            logger.warning("LLM gagal/tidak tersedia — menggunakan fallback plan.")
            plan_data = self._generate_fallback_plan(sitrep)

        plan_data["situation_report_id"] = sitrep["id"]
        plan_data["earthquake_id"]       = earthquake_id

        plan_id = self.db.insert_coordination_plan(plan_data)
        if plan_id:
            plan_data["id"] = plan_id
            logger.info(f"Coordination plan tersimpan (ID={plan_id}) untuk gempa {earthquake_id}")
            return plan_data

        logger.error(f"Gagal menyimpan coordination plan untuk gempa {earthquake_id}")
        return None


# ─────────────────────────────────────────────────────────────
#  Test standalone
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s  [%(levelname)-8s]  %(name)s: %(message)s")
    agent = CoordinationAgent()
    from database.db_handler import DatabaseHandler
    db = DatabaseHandler()
    sitreps = db.get_all_situation_reports(limit=1)
    if sitreps:
        eq_id = sitreps[0]["earthquake_id"]
        plan = agent.run(eq_id)
        if plan:
            print(f"\nPlan untuk gempa {eq_id}:")
            print(f"  Resource mapping: {plan['resource_mapping'][:100]}…")
            print(f"  {len(plan['action_priorities'])} aksi prioritas")
            print(f"  Timeline: {plan['estimated_timeline']}")
    else:
        print("Tidak ada sitrep di database.")
