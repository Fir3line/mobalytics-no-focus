@echo off
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (python patch_mobalytics.py undo) else (py -3 patch_mobalytics.py undo)
pause
