@echo off
setlocal
cd /d "%~dp0"
title BlockAttend - REAL Solidity Blockchain + Face Recognition
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_one_click.ps1" -Mode Ethereum
if errorlevel 1 (
 echo.
 echo Setup or startup failed. Read the red error message above.
 echo You can also use START_OFFLINE_DEMO_WINDOWS.bat for the no-Node educational demonstration.
 pause
)
