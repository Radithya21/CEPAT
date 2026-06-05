"""
intelligence_agent.py — CEPAT Intelligence Agent (Fase 2)
Scraping berita dari RSS feed, filter keyword gempa,
dan klasifikasi kredibilitas artikel menggunakan Claude API.
"""

import asyncio
import json
import logging
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import (
    EARTHQUAKE_KEYWORDS,
    LLM_REQUEST_DELAY,
    PIPELINE_MAX_INTEL_PER_EQ,
    RSS_FEEDS,
    RSS_MAX_AGE_HOURS,
    RSS_TIMEOUT_SEC,
    TELEGRAM_API_HASH,
    TELEGRAM_API_ID,
    TELEGRAM_CHANNELS,
    TELEGRAM_MAX_MSGS,
    TELEGRAM_SESSION_DIR,
)
from database.db_handler import DatabaseHandler
from utils.llm_client import LLMClient

logger = logging.getLogger("IntelligenceAgent")

PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "prompts"
)


def _load_prompt(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class IntelligenceAgent:
    """
    Agent pemantau sumber berita terkait gempa.

    Cara pakai:
        agent = IntelligenceAgent()
        reports = agent.run(earthquake)   # earthquake: dict dari DB
    """

    def __init__(self, db_handler: DatabaseHandler = None):
        self.db = db_handler or DatabaseHandler()
        self._llm = LLMClient()
        self._hoax_prompt_template = _load_prompt("hoax_filter.txt")
        logger.info("IntelligenceAgent siap — menggunakan LLMClient (Groq → Ollama → Fallback).")

    # ─────────────────────────────────────────────────────────
    #  RSS Fetching
    # ─────────────────────────────────────────────────────────

    def _fetch_feed(self, name: str, url: str) -> list[dict]:
        """Fetch dan parse satu RSS feed. Return list artikel mentah."""
        try:
            # feedparser.parse bisa lambat, beri timeout via requests
            resp = requests.get(
                url,
                timeout=RSS_TIMEOUT_SEC,
                headers={"User-Agent": "CEPAT-EmergencyMonitor/1.0"},
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            articles = []
            cutoff = datetime.now(timezone.utc) - timedelta(hours=RSS_MAX_AGE_HOURS)

            for entry in feed.entries:
                # Parse waktu publikasi
                pub_str = entry.get("published", "")
                pub_dt = None
                if pub_str:
                    try:
                        pub_dt = parsedate_to_datetime(pub_str)
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        if pub_dt < cutoff:
                            continue  # Artikel terlalu lama
                    except Exception:
                        pass  # Tidak bisa parse waktu, tetap ambil

                # Ambil konten
                content = ""
                if entry.get("summary"):
                    content = entry.summary
                elif entry.get("content"):
                    content = entry.content[0].value if entry.content else ""

                # Bersihkan HTML tags
                content = re.sub(r"<[^>]+>", " ", content).strip()

                articles.append(
                    {
                        "source_name": name,
                        "source_url": entry.get("link", ""),
                        "source_type": "news_rss",
                        "title": entry.get("title", "").strip(),
                        "content": content[:2000],
                        "published_at": pub_str,
                    }
                )

            logger.info(f"Feed '{name}': {len(articles)} artikel ditemukan")
            return articles

        except requests.exceptions.ConnectionError:
            logger.warning(f"Tidak bisa akses feed '{name}' (ConnectionError)")
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout saat mengakses feed '{name}'")
        except Exception as e:
            logger.error(f"Error saat fetch feed '{name}': {e}")
        return []

    def _fetch_telegram_messages(self) -> list[dict]:
        """
        Fetch pesan terbaru dari Telegram channels yang dikonfigurasi.
        Membutuhkan TELEGRAM_API_ID dan TELEGRAM_API_HASH di environment.
        Jika tidak diset, return list kosong (silent skip).
        """
        if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
            logger.debug(
                "Telegram API credentials tidak diset — skip Telegram monitoring."
            )
            return []

        try:
            from telethon import TelegramClient
            from telethon.tl.types import Message
        except ImportError:
            logger.warning(
                "Package 'telethon' tidak ditemukan. Jalankan: pip install telethon>=1.36.0"
            )
            return []

        async def _async_fetch():
            session_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                TELEGRAM_SESSION_DIR,
                "cepat_telegram",
            )
            articles = []
            try:
                client = TelegramClient(
                    session_path, int(TELEGRAM_API_ID), TELEGRAM_API_HASH
                )
                await client.connect()

                if not await client.is_user_authorized():
                    logger.warning(
                        "Telegram client belum terautentikasi. Jalankan autentikasi manual terlebih dahulu."
                    )
                    await client.disconnect()
                    return []

                for channel in TELEGRAM_CHANNELS:
                    try:
                        msgs = await client.get_messages(
                            channel, limit=TELEGRAM_MAX_MSGS
                        )
                        for msg in msgs:
                            if not isinstance(msg, Message) or not msg.text:
                                continue
                            text = msg.text.lower()
                            if not any(kw in text for kw in EARTHQUAKE_KEYWORDS):
                                continue
                            pub_str = (
                                msg.date.strftime("%a, %d %b %Y %H:%M:%S +0000")
                                if msg.date
                                else ""
                            )
                            articles.append(
                                {
                                    "source_name": f"Telegram:{channel}",
                                    "source_url": f"https://t.me/{channel}/{msg.id}",
                                    "source_type": "telegram",
                                    "title": msg.text[:100].replace("\n", " "),
                                    "content": msg.text[:2000],
                                    "published_at": pub_str,
                                }
                            )
                        logger.info(
                            f"Telegram @{channel}: "
                            f"{len([m for m in msgs if isinstance(m, Message) and m.text])} pesan, "
                            f"relevan: {sum(1 for a in articles if f'Telegram:{channel}' == a['source_name'])}"
                        )
                    except Exception as e:
                        logger.warning(f"Gagal fetch Telegram channel @{channel}: {e}")

                await client.disconnect()
            except Exception as e:
                logger.error(f"Telegram client error: {e}")
            return articles

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_async_fetch())
            loop.close()
            return result
        except Exception as e:
            logger.error(f"Error menjalankan Telegram fetch: {e}")
            return []

    def _fetch_all_feeds(self) -> list[dict]:
        """Fetch semua RSS feed dan Telegram channels yang dikonfigurasi."""
        all_articles = []
        for name, url in RSS_FEEDS.items():
            articles = self._fetch_feed(name, url)
            all_articles.extend(articles)
            time.sleep(0.3)  # Jeda kecil agar tidak flood server

        # Tambahkan dari Telegram (jika dikonfigurasi)
        telegram_articles = self._fetch_telegram_messages()
        if telegram_articles:
            all_articles.extend(telegram_articles)
            logger.info(f"Total artikel Telegram: {len(telegram_articles)}")

        logger.info(f"Total artikel dari semua sumber: {len(all_articles)}")
        return all_articles

    # ─────────────────────────────────────────────────────────
    #  Keyword Filtering
    # ─────────────────────────────────────────────────────────

    def _is_relevant(self, article: dict, earthquake: dict) -> bool:
        """Periksa apakah artikel relevan dengan gempa ini."""
        text = (article.get("title", "") + " " + article.get("content", "")).lower()

        # Harus mengandung minimal 1 keyword umum gempa
        if not any(kw in text for kw in EARTHQUAKE_KEYWORDS):
            return False

        return True

    def _extract_location_keywords(self, location_desc: str) -> list[str]:
        """Ekstrak kata kunci lokasi dari deskripsi BMKG."""
        # Format BMKG: "67 km BaratLaut TIMORTENGAHUT-NTT"
        # Ambil bagian setelah arah mata angin
        directions = [
            "utara",
            "selatan",
            "timur",
            "barat",
            "laut",
            "daya",
            "tenggara",
            "timurlaut",
            "baratlaut",
        ]
        words = location_desc.lower().split()
        location_words = []
        found_dir = False
        for w in words:
            if any(d in w for d in directions):
                found_dir = True
                continue
            if found_dir and len(w) > 3:
                # Hapus kode provinsi seperti -NTT, -SUMUT
                clean = w.split("-")[0]
                if len(clean) > 3:
                    location_words.append(clean)
        return location_words

    # ─────────────────────────────────────────────────────────
    #  Claude Hoax Classification
    # ─────────────────────────────────────────────────────────

    def _classify_credibility(self, article: dict) -> dict:
        """
        Klasifikasi kredibilitas artikel menggunakan LLMClient.
        Return {"status": "VALID|HOAX|UNVERIFIED", "reasoning": "..."}.
        """
        try:
            prompt = self._hoax_prompt_template.format(
                source=article.get("source_name", "Unknown"),
                title=article.get("title", ""),
                content=article.get("content", "")[:1500],
            )
        except KeyError as e:
            logger.error(
                f"Template hoax_filter.txt error — placeholder tidak valid: {e}"
            )
            return {
                "status": "UNVERIFIED",
                "reasoning": "Gagal memformat prompt — template error.",
            }

        raw_text = self._llm.generate(prompt, max_tokens=256)
        if not raw_text:
            return {
                "status": "UNVERIFIED",
                "reasoning": "LLM tidak tersedia — semua provider gagal.",
            }

        try:
            json_match = re.search(r"\{[^{}]*\}", raw_text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                status = result.get("status", "UNVERIFIED").upper()
                if status not in ("VALID", "HOAX", "UNVERIFIED"):
                    status = "UNVERIFIED"
                return {
                    "status": status,
                    "reasoning": result.get("reasoning", ""),
                }

            logger.warning(
                f"Respons LLM tidak mengandung JSON valid: {raw_text[:100]}"
            )
        except json.JSONDecodeError as e:
            logger.warning(f"Gagal parse JSON dari LLM: {e}")
        except Exception as e:
            logger.error(f"Error saat klasifikasi LLM: {e}")

        return {"status": "UNVERIFIED", "reasoning": "Gagal mengklasifikasi."}

    # ─────────────────────────────────────────────────────────
    #  Main Run
    # ─────────────────────────────────────────────────────────

    def run(self, earthquake: dict) -> list[dict]:
        """
        Jalankan intelligence collection untuk satu gempa.
        Return list intelligence report yang sudah disimpan ke DB.
        """
        eq_id = earthquake["id"]
        eq_loc = earthquake.get("location_desc", "")
        eq_mag = earthquake.get("magnitude", 0)

        logger.info(
            f"IntelligenceAgent: memproses gempa ID={eq_id} M{eq_mag} — {eq_loc}"
        )

        # 1. Fetch semua feeds
        all_articles = self._fetch_all_feeds()
        if not all_articles:
            logger.warning("Tidak ada artikel dari RSS feed.")
            return []

        # 2. Filter relevan
        relevant = [a for a in all_articles if self._is_relevant(a, earthquake)]
        logger.info(f"Artikel relevan: {len(relevant)}/{len(all_articles)}")

        # Batasi jumlah artikel yang diproses
        relevant = relevant[:PIPELINE_MAX_INTEL_PER_EQ]

        # 3. Klasifikasi & simpan ke DB
        saved_reports = []
        for article in relevant:
            classification = self._classify_credibility(article)

            report = {
                "earthquake_id": eq_id,
                "source_name": article["source_name"],
                "source_url": article["source_url"],
                "source_type": article.get("source_type", "news_rss"),
                "title": article["title"],
                "content": article["content"],
                "credibility_status": classification["status"],
                "llm_reasoning": classification["reasoning"],
                "published_at": article.get("published_at", ""),
            }

            report_id = self.db.insert_intelligence_report(report)
            if report_id:
                report["id"] = report_id
                saved_reports.append(report)

                status_icon = {"VALID": "✔", "HOAX": "✘", "UNVERIFIED": "?"}.get(
                    classification["status"], "?"
                )
                logger.info(
                    f"  [{status_icon}] {classification['status']:10} | "
                    f"{article['source_name']:8} | {article['title'][:60]}"
                )

            time.sleep(max(0.2, LLM_REQUEST_DELAY / 2))  # Rate limit antar artikel

        logger.info(
            f"IntelligenceAgent selesai: {len(saved_reports)} laporan disimpan untuk gempa {eq_id}"
        )
        return saved_reports
