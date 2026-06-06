@echo off
:: ═══════════════════════════════════════════════════════════════
::  CEPAT — Demo Expo Launcher
::  Double-click file ini untuk langsung jalankan demo expo
:: ═══════════════════════════════════════════════════════════════
chcp 65001 > nul
title CEPAT — AI Orchestrator Demo

:: Masuk ke direktori project
cd /d "%~dp0"

:menu
cls
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║   CEPAT — AI Orchestrator EXPO LAUNCHER                 ║
echo  ║   Pilih mode demo:                                       ║
echo  ║                                                          ║
echo  ║   [1] FULL DEMO    - Semua agent (3-5 menit)            ║
echo  ║   [2] FAST DEMO    - Skip Intel Agent (~30 detik)        ║
echo  ║   [3] CEK STATUS   - Cek Groq dan Ollama sebelum demo     ║
echo  ║   [4] KELUAR                                             ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

set /p choice="  Pilih [1/2/3/4]: "

if "%choice%"=="1" (
    echo.
    echo  [*] Memulai Full Demo...
    echo.
    :: Start Ollama di background - jika belum berjalan
    curl -s http://localhost:11434/api/tags > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo  [*] Memulai Ollama di background...
        start /B ollama serve
        timeout /t 3 /nobreak > nul
    )
    python demo_expo.py --simulate
    echo.
    pause
    goto menu
)

if "%choice%"=="2" (
    echo.
    echo  [*] Memulai Fast Demo - 30 detik...
    echo.
    :: Start Ollama di background - jika belum berjalan
    curl -s http://localhost:11434/api/tags > nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo  [*] Memulai Ollama di background...
        start /B ollama serve
        timeout /t 3 /nobreak > nul
    )
    python demo_expo.py --simulate --fast
    echo.
    pause
    goto menu
)

if "%choice%"=="3" (
    echo.
    python demo_expo.py --status
    echo.
    pause
    goto menu
)

if "%choice%"=="4" (
    exit /b
)

goto menu
