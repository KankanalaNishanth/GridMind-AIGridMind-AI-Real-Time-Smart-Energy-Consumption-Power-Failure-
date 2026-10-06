@echo off
title GridMind AI - Operations Dashboard
echo ===================================================================
echo   ⚡ GridMind AI — Real-Time Smart Energy ^& Power Failure System
echo ===================================================================
echo Starting Backend and launching Frontend Web Dashboard...
cd /d "%~dp0"

if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_server.py
) else if exist "GridMind-AIGridMind-AI-Real-Time-Smart-Energy-Consumption-Power-Failure--main\venv\Scripts\python.exe" (
    "GridMind-AIGridMind-AI-Real-Time-Smart-Energy-Consumption-Power-Failure--main\venv\Scripts\python.exe" run_server.py
) else if exist "..\venv\Scripts\python.exe" (
    "..\venv\Scripts\python.exe" run_server.py
) else (
    python run_server.py
)
pause
