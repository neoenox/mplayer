@echo off
REM One-command verification: build venv, install deps, run all tests (silent).
REM Usage: check.bat
setlocal
set "APP_DIR=%~dp0"
set "PY=%APP_DIR%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo setup: creating .venv ...
  python -m venv "%APP_DIR%.venv"
  if errorlevel 1 (
    echo ERROR: failed to create venv (need Python 3.11 on PATH)
    exit /b 1
  )
)
echo setup: installing requirements ...
"%APP_DIR%.venv\Scripts\pip.exe" install -r "%APP_DIR%requirements.txt"
if errorlevel 1 (
  echo ERROR: pip install failed
  exit /b 1
)
echo setup: pip check ...
"%APP_DIR%.venv\Scripts\pip.exe" check
if errorlevel 1 (
  echo ERROR: pip check failed
  exit /b 1
)
echo test: running stages ...
"%PY%" "%APP_DIR%tests\run_all.py" %*
