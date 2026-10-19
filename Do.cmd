@echo off
cd /d "%~dp0"
echo This changes Mobalytics' publisher signature. Read README.md first.
choice /c YN /n /m "Apply the patch? [Y/N] "
if errorlevel 2 exit /b 0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Patch-Mobalytics.ps1" -Action Do -AcceptSignatureChange
pause
