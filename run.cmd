@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo FilePlotter environment is missing.
  echo Expected interpreter: %~dp0.venv\Scripts\python.exe
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 "%~dp0main.py" %*
