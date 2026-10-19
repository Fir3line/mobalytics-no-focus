@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Patch-Mobalytics.ps1" -Action Undo
pause
