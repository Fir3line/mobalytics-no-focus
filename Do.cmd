@echo off
cd /d "%~dp0"
echo This changes Mobalytics' publisher signature. Read README.md first.
choice /c YN /n /m "Apply the patch? [Y/N] "
if errorlevel 2 exit /b 0
where py >nul 2>nul
if errorlevel 1 (python patch_mobalytics.py do --accept-signature-change) else (py -3 patch_mobalytics.py do --accept-signature-change)
pause
