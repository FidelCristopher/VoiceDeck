@echo off
cd /d %~dp0
echo ==========================================
echo       VoiceDeck - Pitch Voice Assistant
echo ==========================================
if not exist ".venv\Scripts\python.exe" (
    echo [VoiceDeck] Virtual environment not found. Setting up...
    python -m venv .venv
    .\.venv\Scripts\pip install -r requirements.txt
)

echo [VoiceDeck] Launching VoiceDeck...
.\.venv\Scripts\python.exe main.py
pause
