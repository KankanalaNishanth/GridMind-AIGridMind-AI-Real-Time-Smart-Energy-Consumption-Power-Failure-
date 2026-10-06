"""
GridMind AI — Unified Server Launcher
Starts the FastAPI Backend and serves the Interactive Frontend UI.
"""
import os
import sys
import time
import threading
import webbrowser

# Add current directory to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import uvicorn

def open_browser():
    """Wait for server to start, then launch default web browser."""
    time.sleep(1.8)
    url = "http://localhost:8000"
    print(f"\n[GridMind AI] Launching Web Dashboard in browser: {url}\n")
    try:
        webbrowser.open(url)
    except Exception as e:
        print(f"Could not automatically launch browser: {e}")

if __name__ == "__main__":
    print("=" * 65)
    print("  ⚡ GridMind AI — Real-Time Energy & Power Failure System")
    print("  State Distribution: TGSPDCL / TGNPDCL")
    print("=" * 65)
    print("  * Web Dashboard  : http://localhost:8000")
    print("  * REST API Docs  : http://localhost:8000/docs")
    print("  * Alternative Doc: http://localhost:8000/redoc")
    print("=" * 65)
    print("Starting Uvicorn server on http://0.0.0.0:8000 ... (Press Ctrl+C to stop)")

    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False, log_level="info")
