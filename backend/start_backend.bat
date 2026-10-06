@echo off
title GridMind AI - Backend API Service
echo ===================================================================
echo   ⚡ GridMind AI — Backend API Service Launcher
echo ===================================================================
echo Starting FastAPI Backend on http://localhost:8000 ...
cd /d "%~dp0"

if exist "..\venv\Scripts\python.exe" (
    "..\venv\Scripts\python.exe" run_server.py
) else if exist "..\GridMind-AIGridMind-AI-Real-Time-Smart-Energy-Consumption-Power-Failure--main\venv\Scripts\python.exe" (
    "..\GridMind-AIGridMind-AI-Real-Time-Smart-Energy-Consumption-Power-Failure--main\venv\Scripts\python.exe" run_server.py
) else if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" run_server.py
) else (
    python run_server.py
)
pause
