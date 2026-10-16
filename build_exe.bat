@echo off
REM Build a standalone Windows distribution of mplayer with PyInstaller.
REM Output: dist\mplayer\mplayer.exe (portable folder).
REM Usage: build_exe.bat
setlocal
set "APP_DIR=%~dp0"
set "PY=%APP_DIR%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: .venv not found. Run check.bat first to set up the environment.
  exit /b 1
)
echo build: installing build requirements ...
"%APP_DIR%.venv\Scripts\pip.exe" install -r "%APP_DIR%requirements-build.txt"
if errorlevel 1 (
  echo ERROR: failed to install build requirements
  exit /b 1
)
echo build: running PyInstaller ...
"%PY%" -m PyInstaller --noconfirm --clean "%APP_DIR%mplayer.spec"
if errorlevel 1 (
  echo ERROR: PyInstaller build failed
  exit /b 1
)
echo build: verifying frozen exe (self-test) ...
"%APP_DIR%dist\mplayer\mplayer.exe" --selftest "%APP_DIR%test_640x360.mp4" --selftest-out "%APP_DIR%dist\selftest.json"
if errorlevel 1 (
  echo ERROR: frozen exe self-test failed
  exit /b 1
)
echo build: OK -^> "%APP_DIR%dist\mplayer\mplayer.exe"
endlocal
