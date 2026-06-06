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
_DIM    = "\033[2m"

# Retry configuration
_GROQ_MAX_RETRIES    = 2      # Coba ulang max 2x sebelum fallback Ollama
_GROQ_RETRY_WAIT_SEC = 6.0   # Tunggu 6 detik antara retry (setelah rate limit 429)


class LLMClient:
    """
    Unified LLM client dengan fallback otomatis:
      1. Groq API  (cloud, cepat, gratis — llama-3.1-8b-instant)
      2. Ollama    (lokal, offline, qwen2.5:7b — tidak ada rate limit)
      3. None      → agent akan pakai rule-based fallback

    Attributes:
        last_provider (str): Provider terakhir yang berhasil ('groq', 'ollama', 'none')
        groq_call_count (int): Jumlah request ke Groq dalam session ini
        ollama_call_count (int): Jumlah request ke Ollama dalam session ini
    """

    def __init__(self):
        self.last_provider: str = "none"
        self.groq_call_count   = 0
        self.ollama_call_count = 0
        self._groq_available   = bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_XXX"))
        self._ollama_available = self._check_ollama()
        self._groq_consecutive_errors = 0  # Track consecutive errors untuk auto-disable sementara

        # Log status provider saat inisialisasi
        self._print_provider_banner()

    def _print_provider_banner(self):
        """Print banner status provider yang menarik untuk expo."""
        groq_status   = f"{_GREEN}✔ READY{_RESET}" if self._groq_available   else f"{_RED}✘ No API Key / Invalid{_RESET}"
        ollama_status = f"{_GREEN}✔ READY{_RESET}" if self._ollama_available else f"{_YELLOW}⚠ Not Running{_RESET}"

        logger.info("╔══════════════════════════════════════════════════╗")
        logger.info("║            CEPAT — LLM Provider Status           ║")
        logger.info("╠══════════════════════════════════════════════════╣")
        logger.info(f"║  🌐 Groq   [{GROQ_MODEL:<22}] {groq_status}")
        logger.info(f"║  💻 Ollama [{OLLAMA_MODEL:<22}] {ollama_status}")
        if self._groq_available and self._ollama_available:
            logger.info("║  📡 Mode: HYBRID (Groq Primary → Ollama Fallback)")
        elif self._groq_available:
            logger.info("║  📡 Mode: GROQ ONLY (setup Ollama untuk backup)")
        elif self._ollama_available:
            logger.info("║  📡 Mode: OLLAMA LOCAL ONLY")
        else:
            logger.info("║  📡 Mode: RULE-BASED ONLY (no LLM)")
        logger.info("╚══════════════════════════════════════════════════╝")

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
                    logger.info(f"Ollama OK — model '{OLLAMA_MODEL}' tersedia di lokal.")
                else:
                    logger.warning(
                        f"Ollama berjalan tapi model '{OLLAMA_MODEL}' belum didownload. "
                        f"Jalankan: ollama pull {OLLAMA_MODEL}"
                    )
                    return False
                return True
        except requests.exceptions.ConnectionError:
            logger.info("Ollama tidak berjalan — akan skip ke fallback rule-based jika Groq gagal.")
        except Exception as e:
            logger.warning(f"Ollama check error: {e}")
        return False

    def refresh_status(self):
        """Refresh status provider (untuk re-check setelah Ollama distart)."""
        self._groq_available   = bool(GROQ_API_KEY and not GROQ_API_KEY.startswith("gsk_XXX"))
        self._ollama_available = self._check_ollama()
        self._groq_consecutive_errors = 0
        self._print_provider_banner()

    # ─────────────────────────────────────────────────────────
    #  Groq Generation (dengan Retry Logic)
    # ─────────────────────────────────────────────────────────

    def _generate_groq(self, prompt: str, max_tokens: int) -> str | None:
        """
        Panggil Groq API dengan retry otomatis.
        - Retry hingga _GROQ_MAX_RETRIES kali jika rate limit (429)
        - Tunggu _GROQ_RETRY_WAIT_SEC detik sebelum retry
        - Return teks atau None jika semua retry gagal
        """
        if not self._groq_available:
            return None

        for attempt in range(1, _GROQ_MAX_RETRIES + 1):
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
                    self.groq_call_count += 1
                    self._groq_consecutive_errors = 0
                    logger.info(
                        f"  {_GREEN}[Groq ✔]{_RESET} Response OK "
                        f"({len(text)} chars | call #{self.groq_call_count})"
                    )
                    return text.strip()

            except Exception as e:
                err_str = str(e)

                # Rate limit (429) — retry dengan wait
                if "429" in err_str or "rate_limit" in err_str.lower():
                    self._groq_consecutive_errors += 1
                    if attempt < _GROQ_MAX_RETRIES:
                        wait_time = _GROQ_RETRY_WAIT_SEC * attempt
                        logger.warning(
                            f"  {_YELLOW}[Groq ⚠]{_RESET} Rate limit! "
                            f"Retry {attempt}/{_GROQ_MAX_RETRIES - 1} dalam {wait_time:.0f}s..."
                        )
                        time.sleep(wait_time)
                        continue
                    else:
                        logger.warning(
                            f"  {_YELLOW}[Groq ⚠]{_RESET} Rate limit — "
                            f"switching ke Ollama lokal..."
                        )

                # API key invalid — disable permanen untuk session ini
                elif "401" in err_str or "invalid_api_key" in err_str.lower():
                    logger.error(
                        f"  {_RED}[Groq ✘]{_RESET} API Key tidak valid! "
                        f"Cek GROQ_API_KEY di .env"
                    )
                    self._groq_available = False
                    return None

                # Error lainnya
                else:
                    logger.warning(f"  {_YELLOW}[Groq ⚠]{_RESET} Error: {err_str[:120]}")
                    if attempt < _GROQ_MAX_RETRIES:
                        time.sleep(2)
                        continue

                break  # Keluar dari retry loop

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
                self.ollama_call_count += 1
                logger.info(
                    f"  {_CYAN}[Ollama ✔]{_RESET} Response OK "
                    f"({len(text)} chars | call #{self.ollama_call_count})"
                )
                return text.strip()
        except requests.exceptions.Timeout:
            logger.warning(
                f"  {_YELLOW}[Ollama ⚠]{_RESET} Timeout ({OLLAMA_TIMEOUT}s) — "
                f"coba naikkan OLLAMA_TIMEOUT di .env"
            )
        except requests.exceptions.ConnectionError:
            logger.warning(
                f"  {_YELLOW}[Ollama ⚠]{_RESET} Connection error — "
                f"Ollama belum distart? Jalankan: ollama serve"
            )
            self._ollama_available = False
        except Exception as e:
            logger.warning(f"  {_YELLOW}[Ollama ⚠]{_RESET} Error: {str(e)[:120]}")
        return None

    # ─────────────────────────────────────────────────────────
    #  Main Generate (dengan fallback)
    # ─────────────────────────────────────────────────────────

    def generate(self, prompt: str, max_tokens: int = 1500) -> str | None:
        """
        Generate teks dari LLM dengan fallback otomatis.

        Urutan:
          1. Groq API (jika GROQ_API_KEY valid) — dengan retry otomatis
          2. Ollama lokal (jika server berjalan & model tersedia)
          3. Return None → agent pakai rule-based fallback

        Args:
            prompt:     Prompt teks lengkap
            max_tokens: Maks token output

        Return:
            str  → teks hasil LLM
            None → semua provider gagal, gunakan rule-based fallback
        """
        # Tambahkan delay kecil untuk hindari burst request ke Groq
        if LLM_REQUEST_DELAY > 0:
            time.sleep(LLM_REQUEST_DELAY)

        # 1. Coba Groq (dengan retry logic)
        result = self._generate_groq(prompt, max_tokens)
        if result:
            self.last_provider = "groq"
            return result

        # 2. Coba Ollama (fallback lokal, tidak ada rate limit)
        if self._ollama_available:
            logger.info(f"  {_CYAN}[Ollama]{_RESET} Menggunakan Ollama lokal sebagai fallback...")
            result = self._generate_ollama(prompt, max_tokens)
            if result:
                self.last_provider = "ollama"
                return result

        # 3. Semua gagal → rule-based fallback
        self.last_provider = "none"
        logger.warning(
            f"  {_RED}[LLM ✘]{_RESET} Semua provider gagal — "
            f"agent akan pakai rule-based fallback"
        )
        return None

    @staticmethod
    def extract_json(raw: str) -> dict | None:
        r"""
        Ekstrak dan parse JSON dari raw response LLM dengan sangat robust:
          - Membersihkan karakter kontrol ASCII yang tidak valid
          - Mendeteksi markdown code block (```json ... ```)
          - Menangani baris baru (\n) yang tidak di-escape dalam string
          - Menangani backslash (\) ilegal dengan meng-escape-nya
        """
        if not raw or not isinstance(raw, str):
            return None

        try:
            import re
            # 1. Bersihkan karakter kontrol ASCII yang sering muncul dari LLM response
            clean_raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)

            # 2. Coba ekstrak JSON dari markdown code block dulu
            code_block = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', clean_raw, re.DOTALL)
            if code_block:
                json_str = code_block.group(1)
            else:
                # Fallback: cari JSON object langsung
                json_match = re.search(r'\{.*\}', clean_raw, re.DOTALL)
                if not json_match:
                    return None
                json_str = json_match.group()

            # 3. Normalisasi newline dalam string JSON (ganti literal \n dengan spasi)
            json_str = re.sub(r'(?<!\\)\n', ' ', json_str)
            json_str = re.sub(r'\s+', ' ', json_str)  # Normalize multiple spaces

            # 4. Sanitasi backslash (\) ilegal agar tidak menyebabkan JSONDecodeError (Invalid \escape)
            # Regex ini mencocokkan backslash yang tidak diikuti oleh karakter escape standar JSON
            # (seperti ", \, /, b, f, n, r, t, atau uXXXX)
            json_str = re.sub(r'\\(?!["\\/bfnrt])(?!u[0-9a-fA-F]{4})', r'\\\\', json_str)

            return json.loads(json_str)
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────
    #  Status Info (untuk dashboard / demo expo)
    # ─────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Return status semua provider untuk ditampilkan di dashboard."""
        return {
            "groq_available":    self._groq_available,
            "groq_model":        GROQ_MODEL,
            "groq_call_count":   self.groq_call_count,
            "ollama_available":  self._ollama_available,
            "ollama_model":      OLLAMA_MODEL,
            "ollama_call_count": self.ollama_call_count,
            "last_provider":     self.last_provider,
            "mode": (
                "hybrid"      if self._groq_available and self._ollama_available else
                "groq_only"   if self._groq_available else
                "ollama_only" if self._ollama_available else
                "fallback"
            ),
        }
