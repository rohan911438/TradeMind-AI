@echo off
REM One-click start for TradeMind AI (Windows)
cd /d "%~dp0backend"
if not exist .venv (
  echo Creating virtual environment...
  py -3.11 -m venv .venv
  .venv\Scripts\python.exe -m pip install -r requirements.txt
)
if not exist models\xgb_model.json .venv\Scripts\python.exe -m app.predictx.train
start "" http://localhost:8000
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
