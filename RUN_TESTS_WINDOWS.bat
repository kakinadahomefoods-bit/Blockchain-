@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
 echo First start the project with START_PROJECT_WINDOWS.bat to install Python dependencies.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
pause
