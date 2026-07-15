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
    "Personnel": {
        "SAR Team": 2,
        "BPBD Officers": 15,
        "Trained Volunteers": 30,
        "Medical Staff (doctors/nurses)": 8,
    },
    "Logistics": {
        "Food packages": 500,
        "Refugee tents (10-person capacity)": 20,
        "Blankets / mattresses": 200,
        "Basic medicines": "1 container",
        "Clean water (liters)": 10000,
    },
    "Equipment & Vehicles": {
        "Excavator": 1,
        "Ambulance": 3,
        "BPBD rescue vehicle": 2,
        "Rubber boat": 4,
        "Portable generator": 5,
        "Mapping drone": 1,
    },
}

_FALLBACK_ACTIONS = {
    "CRITICAL": [
        {"priority": "P1", "action": "Activate Emergency Command Post",
         "description": "Activate the Emergency Command Center, declare Alert Level I, coordinate with BNPB and TNI/Police.", "timeline_hours": 1},
        {"priority": "P1", "action": "Evacuate Red Zone",
         "description": "Forced evacuation of residents in high-risk zones: coastal areas, steep slopes, and severely damaged buildings.", "timeline_hours": 2},
        {"priority": "P2", "action": "Damage & Casualty Assessment",
         "description": "Deploy SAR and medical teams for rapid assessment of casualties, infrastructure damage, and urgent needs.", "timeline_hours": 4},
        {"priority": "P2", "action": "Emergency Logistics Distribution",
         "description": "Distribute food packages, clean water, tents, and medicines to evacuation posts.", "timeline_hours": 6},
        {"priority": "P3", "action": "Critical Infrastructure Recovery",
         "description": "Prioritize restoration of main road access, electricity network, and health facilities.", "timeline_hours": 24},
    ],
    "HIGH": [
        {"priority": "P1", "action": "Activate Response Team",
         "description": "Activate Alert Level II, deploy BPBD teams and coordinate with relevant agencies.", "timeline_hours": 1},
        {"priority": "P1", "action": "Rapid Field Assessment",
         "description": "Deploy SAR teams for initial damage assessment and victim identification in affected areas.", "timeline_hours": 2},
        {"priority": "P2", "action": "Establish Evacuation Posts",
         "description": "Set up evacuation tents, prepare basic logistics, and ensure clean water availability.", "timeline_hours": 4},
        {"priority": "P2", "action": "Medical Coordination",
         "description": "Activate field medical posts, coordinate with nearest hospitals for treatment of injured victims.", "timeline_hours": 6},
        {"priority": "P3", "action": "Data Collection & Recovery",
         "description": "Record affected residents, distribute further aid, begin infrastructure recovery.", "timeline_hours": 12},
    ],
    "MEDIUM": [
        {"priority": "P1", "action": "Activate Preparedness",
         "description": "Activate Alert Status, BPBD team standby, and monitor situation developments.", "timeline_hours": 1},
        {"priority": "P1", "action": "Monitor Aftershocks",
         "description": "Coordinate with BMKG to monitor aftershocks and secondary hazard potential.", "timeline_hours": 2},
        {"priority": "P2", "action": "Field Verification",
         "description": "Send teams to verify field conditions, building damage, and assistance needs.", "timeline_hours": 4},
        {"priority": "P2", "action": "Public Communication",
         "description": "Disseminate official information through media and social media to prevent panic.", "timeline_hours": 4},
        {"priority": "P3", "action": "Psychosocial Support",
         "description": "Prepare counseling services and psychosocial support for affected residents.", "timeline_hours": 12},
    ],
    "LOW": [
        {"priority": "P1", "action": "Situation Monitoring",
         "description": "Monitor situation developments periodically and coordinate with BMKG.", "timeline_hours": 1},
        {"priority": "P2", "action": "Public Information",
         "description": "Convey official information so the public does not panic and remains alert.", "timeline_hours": 2},
        {"priority": "P2", "action": "BPBD Team Standby",
         "description": "Ensure BPBD team is ready and communication is running smoothly.", "timeline_hours": 3},
        {"priority": "P3", "action": "Monitoring Coordination",
         "description": "Coordinate with relevant agencies for post-earthquake environmental monitoring.", "timeline_hours": 6},
        {"priority": "P3", "action": "Preparedness Evaluation",
         "description": "Conduct preparedness evaluation and ensure all disaster response SOPs are ready to activate.", "timeline_hours": 12},
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
            f"Location       : {sitrep.get('location_desc', '—')}\n"
            f"Time           : {sitrep.get('eq_timestamp', '—')}\n"
            f"Magnitude      : M{sitrep.get('magnitude', '—')}\n"
            f"Risk Level     : {sitrep.get('risk_level', '—')}\n"
            f"Summary        : {sitrep.get('summary', '—')}\n"
            f"Affected Areas : {sitrep.get('affected_areas', '—')}\n"
            f"Recommendations:\n{recs_text}"
        )

    def _format_resources(self) -> str:
        lines = []
        for category, items in DEFAULT_RESOURCES.items():
            lines.append(f"{category}:")
            for item, qty in items.items():
                lines.append(f"  - {item}: {qty}")
        return "\n".join(lines)

    def _format_resource_mapping_result(self, val) -> str:
        if not val:
            return ""
        
        # Jika berupa string, cek apakah berisi representasi serialized JSON atau Python dict
        if isinstance(val, str):
            val_str = val.strip()
            if val_str.startswith("{") and val_str.endswith("}"):
                try:
                    import json
                    parsed_val = json.loads(val_str)
                    val = parsed_val
                except Exception:
                    try:
                        import ast
                        parsed_val = ast.literal_eval(val_str)
                        val = parsed_val
                    except Exception:
                        pass

        if isinstance(val, str):
            return val
        
        if isinstance(val, dict):
            lines = []
            for k, v in val.items():
                if isinstance(v, dict):
                    lines.append(f"【 {k} 】")
                    for sub_k, sub_v in v.items():
                        if isinstance(sub_v, dict):
                            lines.append(f"  * {sub_k}:")
                            for s_k, s_v in sub_v.items():
                                lines.append(f"    - {s_k}: {s_v}")
                        else:
                            lines.append(f"  * {sub_k}: {sub_v}")
                    lines.append("")  # Spasi antar kategori
                else:
                    lines.append(f"• {k}: {v}")
            return "\n".join(lines).strip()
        
        return str(val)

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

        result = LLMClient.extract_json(raw)
        if not result:
            logger.warning("CoordinationAgent: Gagal parse JSON dari LLM.")
            logger.debug(f"Raw LLM response (first 300 chars): {raw[:300]}")
            return None

        try:
            priorities = result.get("action_priorities", [])
            if not isinstance(priorities, list):
                priorities = []

            # Format resource mapping dynamically
            raw_resource_mapping = result.get("resource_mapping", "")
            resource_mapping = self._format_resource_mapping_result(raw_resource_mapping)

            return {
                "resource_mapping":   resource_mapping,
                "action_priorities":  priorities[:5],
                "estimated_timeline": str(result.get("estimated_timeline", "")),
                "generated_by":       f"llm:{self._llm.last_provider}",
            }
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

        # Kebutuhan standar berdasarkan tingkat risiko gempa
        if risk == "CRITICAL":
            req_p = {"SAR Team": 10, "BPBD Officers": 50, "Trained Volunteers": 100, "Medical Staff (doctors/nurses)": 20}
            req_l = {"Food packages": 2000, "Refugee tents (10-person capacity)": 100, "Blankets / mattresses": 800, "Basic medicines": "5 containers", "Clean water (liters)": 50000}
            req_e = {"Excavator": 5, "Ambulance": 10, "BPBD rescue vehicle": 5, "Rubber boat": 10, "Portable generator": 15, "Mapping drone": 2}
        elif risk == "HIGH":
            req_p = {"SAR Team": 5, "BPBD Officers": 30, "Trained Volunteers": 60, "Medical Staff (doctors/nurses)": 12}
            req_l = {"Food packages": 1000, "Refugee tents (10-person capacity)": 50, "Blankets / mattresses": 400, "Basic medicines": "3 containers", "Clean water (liters)": 25000}
            req_e = {"Excavator": 3, "Ambulance": 6, "BPBD rescue vehicle": 3, "Rubber boat": 6, "Portable generator": 10, "Mapping drone": 2}
        elif risk == "MEDIUM":
            req_p = {"SAR Team": 2, "BPBD Officers": 15, "Trained Volunteers": 30, "Medical Staff (doctors/nurses)": 8}
            req_l = {"Food packages": 500, "Refugee tents (10-person capacity)": 20, "Blankets / mattresses": 200, "Basic medicines": "1 container", "Clean water (liters)": 10000}
            req_e = {"Excavator": 1, "Ambulance": 3, "BPBD rescue vehicle": 2, "Rubber boat": 4, "Portable generator": 5, "Mapping drone": 1}
        else: # LOW
            req_p = {"SAR Team": 1, "BPBD Officers": 5, "Trained Volunteers": 10, "Medical Staff (doctors/nurses)": 2}
            req_l = {"Food packages": 100, "Refugee tents (10-person capacity)": 5, "Blankets / mattresses": 50, "Basic medicines": "0 containers", "Clean water (liters)": 2000}
            req_e = {"Excavator": 0, "Ambulance": 1, "BPBD rescue vehicle": 1, "Rubber boat": 1, "Portable generator": 2, "Mapping drone": 0}

        fallback_data = {
            "Personnel": {
                "Available": DEFAULT_RESOURCES["Personnel"],
                "Required": req_p
            },
            "Logistics": {
                "Available": DEFAULT_RESOURCES["Logistics"],
                "Required": req_l
            },
            "Equipment & Vehicles": {
                "Available": DEFAULT_RESOURCES["Equipment & Vehicles"],
                "Required": req_e
            }
        }

        resource_mapping = self._format_resource_mapping_result(fallback_data)
        actions = _FALLBACK_ACTIONS.get(risk, _FALLBACK_ACTIONS["MEDIUM"])
        timeline_map = {"CRITICAL": "72 hours intensive", "HIGH": "48 hours intensive", "MEDIUM": "24 hours monitoring", "LOW": "12 hours monitoring"}

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

        # Bersihkan coordination plan lama untuk gempa ini agar tidak duplikat
        try:
            with self.db._connect() as conn:
                conn.execute("DELETE FROM coordination_plans WHERE earthquake_id = ?", (earthquake_id,))
                conn.commit()
        except Exception as e:
            logger.warning(f"Gagal membersihkan plan lama: {e}")

        logger.info(f"CoordinationAgent: membuat plan untuk gempa ID={earthquake_id} M{sitrep.get('magnitude')}")

        plan_data = self._generate_llm_plan(sitrep)
        if plan_data is None:
            logger.warning("LLM gagal/tidak tersedia — menggunakan fallback plan.")
            plan_data = self._generate_fallback_plan(sitrep)

        # Format action_priorities agar mencakup key 'timeline' untuk frontend React
        actions = plan_data.get("action_priorities", [])
        formatted_actions = []
        for a in actions:
            if isinstance(a, dict):
                a_copy = a.copy()
                hours = a_copy.get("timeline_hours")
                if hours is not None:
                    a_copy["timeline"] = f"+{hours} hours"
                elif a_copy.get("timeline") is None:
                    a_copy["timeline"] = "—"
                formatted_actions.append(a_copy)
        plan_data["action_priorities"] = formatted_actions

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
