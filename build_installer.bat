@echo off
REM Build the portable exe and the Windows installer (Inno Setup).
REM Output: dist\installer\mplayer-setup-<version>.exe
REM Usage: build_installer.bat
setlocal
set "APP_DIR=%~dp0"
set "PY=%APP_DIR%.venv\Scripts\python.exe"
if not exist "%PY%" (
  echo ERROR: .venv not found. Run check.bat first to set up the environment.
  exit /b 1
)

echo installer: building portable exe first ...
call "%APP_DIR%build_exe.bat"
if errorlevel 1 (
  echo ERROR: exe build failed
  exit /b 1
)

echo installer: compiling Inno Setup script ...
"%PY%" "%APP_DIR%tools\make_installer.py"
if errorlevel 1 (
  echo ERROR: installer build failed. Is Inno Setup 6 installed? (set INNO_SETUP to ISCC.exe)
  exit /b 1
)

for %%f in ("%APP_DIR%dist\installer\mplayer-setup-*.exe") do echo installer: OK -^> %%f
endlocal
