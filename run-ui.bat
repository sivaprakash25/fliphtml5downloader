@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt -q
)
.venv\Scripts\uvicorn app:app --host 127.0.0.1 --port 8765 --reload
