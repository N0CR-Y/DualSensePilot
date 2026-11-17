@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Sanal ortam bulunamadi. Once kur.bat dosyasini calistir.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" run.py %*
