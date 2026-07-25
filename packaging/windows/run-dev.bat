@echo off
REM Atalho de desenvolvimento no Windows (sem PyInstaller)
cd /d "%~dp0..\.."
set PRESENT_PEDRO_ROOT=%CD%
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "packaging\windows\launcher.py"
) else (
  python "packaging\windows\launcher.py"
)
pause
