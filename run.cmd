@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo FilePlotter environment is missing.
  echo Run: py -3.12 -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -e ".[test]"
  exit /b 1
)
".venv\Scripts\python.exe" -X utf8 -m fileplotter %*
