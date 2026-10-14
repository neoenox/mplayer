@echo off
REM Simple video player launcher (uses .venv)
REM Usage: run.bat [video-file]
setlocal
set "APP_DIR=%~dp0"
set "PY=%APP_DIR%.venv\Scripts\python.exe"
set "APP=%APP_DIR%main.py"
if not exist "%PY%" (
  echo ERROR: venv python not found: "%PY%"
  echo ERROR: run these first:
  echo ERROR:   python -m venv .venv
  echo ERROR:   .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)
if not exist "%APP%" (
  echo ERROR: main.py not found: "%APP%"
  exit /b 1
)
"%PY%" "%APP%" %*
