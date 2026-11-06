@echo off
setlocal
cd /d "%~dp0"
title BlockAttend - Signed Single Node Offline Demo
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_one_click.ps1" -Mode Local
if errorlevel 1 (
 echo.
 echo See the error message above. Do not delete data containing records.
 pause
)
