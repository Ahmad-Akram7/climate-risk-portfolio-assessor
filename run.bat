@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>&1
if errorlevel 1 (
  echo uv is not installed. Install it from https://docs.astral.sh/uv/ and run this file again.
  pause
  exit /b 1
)

uv sync --locked
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)

start "CRPA API" cmd /k "uv run --locked uvicorn api.main:app --port 8000 --reload"
start "CRPA Dashboard" cmd /k "uv run --locked streamlit run app\dashboard.py --server.port 8502"

echo API:       http://localhost:8000/docs
echo Dashboard: http://localhost:8502
endlocal
