"""
utils/llm_client.py — CEPAT Unified LLM Client
Hierarki provider: Groq API → Ollama Lokal → None (trigger rule-based fallback)

Cara pakai:
    from utils.llm_client import LLMClient
    client = LLMClient()
    response = client.generate(prompt, max_tokens=1500)  # str | None
"""

import json
import logging
import os
import sys
import time

import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    GROQ_API_KEY,
    GROQ_MODEL,
    LLM_REQUEST_DELAY,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
)

logger = logging.getLogger("LLMClient")

# ─────────────────────────────────────────────────────────────
#  Warna terminal (untuk expo demo visual)
# ─────────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_YELLOW = "\033[93m"
_RED    = "\033[91m"
_CYAN   = "\033[96m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"


class LLMClient:
    """
    Unified LLM client dengan fallback otomatis:
      1. Groq API  (cloud, cepat, gratis)
      2. Ollama    (lokal, offline, butuh install)
      3. None      → agent akan pakai rule-based fallback

    Attributes:
        last_provider (str): Provider terakhir yang berhasil ('groq', 'ollama', 'none')
    """

    def __init__(self):
        self.last_provider: str = "none"
        self._groq_available  = bool(GROQ_API_KEY)
        self._ollama_available = self._check_ollama()

        # Log status provider saat inisialisasi
        groq_status   = f"{_GREEN}✔ READY{_RESET}" if self._groq_available   else f"{_RED}✘ No API Key{_RESET}"
        ollama_status = f"{_GREEN}✔ READY{_RESET}" if self._ollama_available else f"{_YELLOW}⚠ Offline/Not Running{_RESET}"

        logger.info(f"LLMClient initialized:")
        logger.info(f"  Groq   [{GROQ_MODEL}]  : {groq_status}")
        logger.info(f"  Ollama [{OLLAMA_MODEL}] : {ollama_status}")

    # ─────────────────────────────────────────────────────────
    #  Provider Health Checks
    # ─────────────────────────────────────────────────────────

    def _check_ollama(self) -> bool:
        """Cek apakah Ollama server aktif dan model tersedia."""
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
            if resp.status_code == 200:
                tags = resp.json()
                models = [m["name"] for m in tags.get("models", [])]
                # Cek apakah model yang dikonfigurasi tersedia
                base_name = OLLAMA_MODEL.split(":")[0]
                available = any(base_name in m for m in models)
                if available:
                    logger.info(f"Ollama OK — model '{OLLAMA_MODEL}' tersedia.")
                else:
                    logger.warning(
                        f"Ollama berjalan tapi model '{OLLAMA_MODEL}' belum didownload. "
                        f"Jalankan: ollama pull {OLLAMA_MODEL}"
                    )
                    return False
                return True
        except requests.exceptions.ConnectionError:
            logger.info("Ollama tidak berjalan (ConnectionError) — akan skip ke fallback.")
        except Exception as e:
            logger.warning(f"Ollama check error: {e}")
        return False

    def refresh_status(self):
        """Refresh status provider (untuk re-check setelah Ollama distart)."""
        self._groq_available  = bool(GROQ_API_KEY)
        self._ollama_available = self._check_ollama()

    # ─────────────────────────────────────────────────────────
    #  Groq Generation
    # ─────────────────────────────────────────────────────────

    def _generate_groq(self, prompt: str, max_tokens: int) -> str | None:
        """Panggil Groq API. Return teks atau None jika gagal."""
        if not self._groq_available:
            return None

        try:
            from groq import Groq
            client = Groq(api_key=GROQ_API_KEY)
            completion = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,
            )
            text = completion.choices[0].message.content
            if text:
                logger.info(f"  {_GREEN}[Groq ✔]{_RESET} Response received ({len(text)} chars)")
                return text.strip()
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str.lower():
                logger.warning(f"  {_YELLOW}[Groq ⚠]{_RESET} Rate limit hit — falling back to Ollama")
            elif "401" in err_str or "invalid_api_key" in err_str.lower():
                logger.error(f"  {_RED}[Groq ✘]{_RESET} Invalid API key — check GROQ_API_KEY in .env")
                self._groq_available = False  # Disable untuk session ini
            else:
                logger.warning(f"  {_YELLOW}[Groq ⚠]{_RESET} Error: {err_str[:100]}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Ollama Generation
    # ─────────────────────────────────────────────────────────

    def _generate_ollama(self, prompt: str, max_tokens: int) -> str | None:
        """Panggil Ollama local server. Return teks atau None jika gagal."""
        if not self._ollama_available:
            return None

        try:
            payload = {
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.3,
                },
            }
            resp = requests.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json=payload,
                timeout=OLLAMA_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            text = result.get("response", "")
            if text:
                logger.info(f"  {_CYAN}[Ollama ✔]{_RESET} Response received ({len(text)} chars)")
                return text.strip()
        except requests.exceptions.Timeout:
            logger.warning(f"  {_YELLOW}[Ollama ⚠]{_RESET} Timeout ({OLLAMA_TIMEOUT}s) — falling back to rule-based")
        except requests.exceptions.ConnectionError:
            logger.warning(f"  {_YELLOW}[Ollama ⚠]{_RESET} Connection error — Ollama tidak berjalan?")
            self._ollama_available = False
        except Exception as e:
            logger.warning(f"  {_YELLOW}[Ollama ⚠]{_RESET} Error: {str(e)[:100]}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Main Generate (dengan fallback)
    # ─────────────────────────────────────────────────────────

    def generate(self, prompt: str, max_tokens: int = 1500) -> str | None:
        """
        Generate teks dari LLM dengan fallback otomatis.

        Urutan:
          1. Groq API (jika GROQ_API_KEY tersedia)
          2. Ollama lokal (jika server berjalan)
          3. Return None → agent pakai rule-based fallback

        Args:
            prompt:     Prompt teks lengkap
            max_tokens: Maks token output

        Return:
            str  → teks hasil LLM
            None → semua provider gagal, gunakan rule-based fallback
        """
        # Tambahkan delay kecil untuk hindari burst request
        if LLM_REQUEST_DELAY > 0:
            time.sleep(LLM_REQUEST_DELAY)

        # 1. Coba Groq
        result = self._generate_groq(prompt, max_tokens)
        if result:
            self.last_provider = "groq"
            return result

        # 2. Coba Ollama
        result = self._generate_ollama(prompt, max_tokens)
        if result:
            self.last_provider = "ollama"
            return result

        # 3. Semua gagal
        self.last_provider = "none"
        logger.warning(
            f"  {_RED}[LLM ✘]{_RESET} Semua provider gagal — agent akan pakai rule-based fallback"
        )
        return None

    # ─────────────────────────────────────────────────────────
    #  Status Info (untuk dashboard / demo)
    # ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return status semua provider untuk ditampilkan di dashboard."""
        return {
            "groq_available":   self._groq_available,
            "groq_model":       GROQ_MODEL,
            "ollama_available": self._ollama_available,
            "ollama_model":     OLLAMA_MODEL,
            "last_provider":    self.last_provider,
        }
