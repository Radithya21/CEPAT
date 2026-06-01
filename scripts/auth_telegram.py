"""
auth_telegram.py — Script untuk autentikasi pertama kali Telegram Client (Telethon).
Menghasilkan session file di database/cepat_telegram.session agar sistem background monitoring
dapat berjalan otomatis tanpa intervensi manual (head Paceless).
"""

import os
import sys
from dotenv import load_dotenv

# Tambahkan path root agar load config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

from config import TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_DIR

def authenticate():
    print("=" * 60)
    print("  CEPAT — Telegram Session Authenticator")
    print("=" * 60)
    
    if not TELEGRAM_API_ID or not TELEGRAM_API_HASH:
        print("ERROR: TELEGRAM_API_ID dan TELEGRAM_API_HASH belum diset di file .env!")
        print("Silakan ikuti langkah berikut:")
        print("1. Salin file .env.example menjadi .env (jika belum ada)")
        print("2. Dapatkan API ID & Hash gratis di: https://my.telegram.org/apps")
        print("3. Isi nilai TELEGRAM_API_ID dan TELEGRAM_API_HASH di dalam file .env")
        sys.exit(1)
        
    print(f"API ID   : {TELEGRAM_API_ID}")
    print(f"API Hash : {TELEGRAM_API_HASH[:6]}...{TELEGRAM_API_HASH[-6:]}")
    print(f"Direktori Session: {TELEGRAM_SESSION_DIR}")
    print("-" * 60)
    
    # Buat direktori session jika belum ada
    os.makedirs(TELEGRAM_SESSION_DIR, exist_ok=True)
    session_path = os.path.join(TELEGRAM_SESSION_DIR, "cepat_telegram")
    
    try:
        from telethon import TelegramClient
    except ImportError:
        print("ERROR: Library 'telethon' belum terinstall!")
        print("Silakan jalankan: pip install telethon")
        sys.exit(1)
        
    print("Menghubungkan ke Telegram...")
    client = TelegramClient(session_path, int(TELEGRAM_API_ID), TELEGRAM_API_HASH)
    
    async def main():
        # start() akan otomatis menanyakan phone number & OTP code jika belum terautentikasi
        await client.start()
        me = await client.get_me()
        print("\n" + "=" * 60)
        print("SUCCESS! Autentikasi Telegram berhasil!")
        print(f"Login sebagai: {me.first_name} {me.last_name or ''} (@{me.username or 'tanpa_username'})")
        print(f"Session file disimpan di: {session_path}.session")
        print("=" * 60)
        print("Background monitoring CEPAT sekarang dapat berjalan otomatis!")
        
    with client:
        client.loop.run_until_complete(main())

if __name__ == "__main__":
    authenticate()
