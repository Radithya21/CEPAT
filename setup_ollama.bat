@echo off
:: ═══════════════════════════════════════════════════════════
::  CEPAT — Ollama Setup Script untuk Windows
::  Jalankan sekali sebelum expo untuk setup Ollama offline backup
:: ═══════════════════════════════════════════════════════════
chcp 65001 > nul
title CEPAT — Ollama Setup

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║       CEPAT — Ollama Offline AI Setup                   ║
echo  ║       Model: qwen2.5:7b (4.7GB download)                ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Cek apakah Ollama sudah terinstall ──────────────────────
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK] Ollama sudah terinstall!
    goto :check_model
) else (
    echo  [!] Ollama belum terinstall.
    echo.
    echo  Silakan download dan install Ollama terlebih dahulu:
    echo.
    echo      https://ollama.com/download/OllamaSetup.exe
    echo.
    echo  Setelah install selesai, jalankan script ini lagi.
    echo.
    start https://ollama.com/download/OllamaSetup.exe
    pause
    exit /b 1
)

:check_model
echo.
echo  [*] Mengecek model qwen2.5:7b...

:: Coba ping Ollama server
curl -s http://localhost:11434/api/tags > nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [*] Memulai Ollama server...
    start /B ollama serve
    timeout /t 3 /nobreak > nul
)

:: Check apakah model sudah ada
ollama list | findstr "qwen2.5" > nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo  [OK] Model qwen2.5:7b sudah tersedia!
    goto :test_model
) else (
    echo  [*] Model belum ada. Memulai download qwen2.5:7b - sekitar 4.7GB...
    echo      Pastikan koneksi internet stabil. Proses ini sekali saja.
    echo.
    ollama pull qwen2.5:7b
    if errorlevel 1 (
        echo.
        echo  [ERROR] Gagal download model. Cek koneksi internet dan coba lagi.
        pause
        exit /b 1
    )
    echo.
    echo  [OK] Model berhasil didownload!
)

:test_model
echo.
echo  [*] Testing Ollama dengan model qwen2.5:7b...
echo.

:: Test sederhana
ollama run qwen2.5:7b "Say 'Ollama ready for CEPAT expo demo!'"

echo.
echo  ══════════════════════════════════════════════════════════
echo   Setup SELESAI! Ollama siap digunakan sebagai backup AI.
echo.
echo   Untuk menggunakan CEPAT:
echo     1. Pastikan Ollama berjalan (sudah otomatis setelah install)
echo     2. Jalankan: python demo_expo.py --simulate
echo     3. Atau fast mode: python demo_expo.py --simulate --fast
echo  ══════════════════════════════════════════════════════════
echo.
pause
