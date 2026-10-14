@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe src\main.py
if errorlevel 1 goto fail
exit /b 0
:fail
echo Startup failed. See README.md for setup requirements.
pause
exit /b 1
