"""
config.py — Konfigurasi Sistem CEPAT
Semua threshold, endpoint API, dan parameter sistem ada di sini.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────
#  BMKG API
# ─────────────────────────────────────────────────────────────
BMKG_LATEST_URL = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"
BMKG_RECENT_URL = "https://data.bmkg.go.id/DataMKG/TEWS/gempaterkini.json"
BMKG_TIMEOUT_SEC = int(os.getenv("BMKG_TIMEOUT", 10))

# ─────────────────────────────────────────────────────────────
#  MONITORING AGENT
# ─────────────────────────────────────────────────────────────
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL", 300))  # default: 5 menit
MAGNITUDE_THRESHOLD = float(os.getenv("MAGNITUDE_THRESHOLD", 5.0))

# ─────────────────────────────────────────────────────────────
#  GEMINI / GOOGLE  (Legacy — tetap ada untuk kompatibilitas)
# ─────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_HOAX_MODEL = os.getenv("GEMINI_HOAX_MODEL", "gemini-2.0-flash")
GEMINI_ANALYSIS_MODEL = os.getenv("GEMINI_ANALYSIS_MODEL", "gemini-2.0-flash")
GEMINI_COMM_MODEL = os.getenv("GEMINI_COMM_MODEL", "gemini-2.0-flash")
GEMINI_COORD_MODEL = os.getenv("GEMINI_COORD_MODEL", "gemini-2.0-flash")
GEMINI_MAX_TOKENS = int(os.getenv("GEMINI_MAX_TOKENS", 1500))

# ─────────────────────────────────────────────────────────────
#  GROQ API  (Primary LLM — Free Tier, high RPM)
# ─────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─────────────────────────────────────────────────────────────
#  OLLAMA  (Fallback — Local inference, offline capable)
# ─────────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_TIMEOUT  = int(os.getenv("OLLAMA_TIMEOUT", 60))

# ─────────────────────────────────────────────────────────────
#  LLM REQUEST SETTINGS
# ─────────────────────────────────────────────────────────────
# Delay antar request ke LLM (detik) — cegah burst rate limit
LLM_REQUEST_DELAY = float(os.getenv("LLM_REQUEST_DELAY", 2.0))

# ─────────────────────────────────────────────────────────────
#  INTELLIGENCE AGENT — RSS Feeds  (Fase 2)
# ─────────────────────────────────────────────────────────────
RSS_FEEDS = {
    "ANTARA": "https://www.antaranews.com/rss/terkini.xml",
    "Detik": "https://rss.detik.com/index.php/detikflash",
    "Tribun": "https://www.tribunnews.com/rss",
    "GNews": "https://news.google.com/rss/search?q=gempa+bumi+indonesia&hl=id&gl=ID&ceid=ID:id",
}
RSS_TIMEOUT_SEC = int(os.getenv("RSS_TIMEOUT", 8))
RSS_MAX_AGE_HOURS = int(os.getenv("RSS_MAX_AGE_HOURS", 24))  # artikel maks 24 jam lalu

EARTHQUAKE_KEYWORDS = [
    "gempa",
    "gempa bumi",
    "tsunami",
    "korban",
    "evakuasi",
    "bpbd",
    "bmkg",
    "magnitudo",
    "skala richter",
    "bencana",
    "aftershock",
    "gempa susulan",
    "seismik",
]

# ─────────────────────────────────────────────────────────────
#  TELEGRAM MONITORING  (T2.6)
# ─────────────────────────────────────────────────────────────
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID", "")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
TELEGRAM_CHANNELS = ["infoBMKG", "BNPBIndonesia", "InfoGempaBMKG"]
TELEGRAM_MAX_MSGS = int(os.getenv("TELEGRAM_MAX_MSGS", "20"))
TELEGRAM_SESSION_DIR = os.getenv("TELEGRAM_SESSION_DIR", "database")

# ─────────────────────────────────────────────────────────────
#  PIPELINE / ORCHESTRATOR  (Fase 2)
# ─────────────────────────────────────────────────────────────
PIPELINE_MIN_MAGNITUDE = float(os.getenv("PIPELINE_MIN_MAGNITUDE", 5.0))
PIPELINE_MAX_INTEL_PER_EQ = int(
    os.getenv("PIPELINE_MAX_INTEL", 10)
)  # maks artikel per gempa

# ─────────────────────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────────────────────
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/cepat.db")

# ─────────────────────────────────────────────────────────────
#  FLASK DASHBOARD
# ─────────────────────────────────────────────────────────────
FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "cepat-secret-key-ganti-di-produksi")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")

# ─────────────────────────────────────────────────────────────
#  OPERATOR AUTH (Hardcoded untuk MVP)
# ─────────────────────────────────────────────────────────────
OPERATORS = {
    "admin": os.getenv("OPERATOR_ADMIN_PASS", "password_bpbd_2025"),
    "operator1": os.getenv("OPERATOR1_PASS", "gempa123"),
    "operator2": os.getenv("OPERATOR2_PASS", "cepat456"),
}
