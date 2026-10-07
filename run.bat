@echo off
setlocal
cd /d "%~dp0"

set "PY=.venv\Scripts\python.exe"

if not exist "%PY%" (
  echo Missing .venv. Run: python -m venv .venv
  echo Then run this file again to install dependencies.
  pause
  exit /b 1
)

"%PY%" -c "import uvicorn, streamlit" >nul 2>&1
if errorlevel 1 (
  echo Installing project dependencies...
  "%PY%" -m pip install -r requirements-dev.txt
  if errorlevel 1 (
    echo Dependency installation failed.
    pause
    exit /b 1
  )
)

start "CRPA API" cmd /k ""%PY%" -m uvicorn api.main:app --port 8000 --reload"
start "CRPA Dashboard" cmd /k ""%PY%" -m streamlit run app\dashboard.py --server.port 8502"

echo API:       http://localhost:8000/docs
echo Dashboard: http://localhost:8502
endlocal
