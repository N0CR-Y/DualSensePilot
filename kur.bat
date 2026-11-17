@echo off
setlocal
cd /d "%~dp0"
echo === DualSensePilot kurulum ===
set PY=
for %%P in (py python python3) do (
    if not defined PY (
        %%P -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set PY=%%P
    )
)
if not defined PY (
    echo Python 3.10+ bulunamadi. https://www.python.org/downloads/ adresinden kur ^(PATH'e ekle^) ya da:
    echo   winget install Python.Python.3.12
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    echo Sanal ortam olusturuluyor...
    %PY% -m venv .venv || (echo venv olusturulamadi & pause & exit /b 1)
)
echo Paketler kuruluyor...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo pip hatasi & pause & exit /b 1)
echo.
echo Kurulum tamam. "DualSensePilot.bat" ile baslat.
echo.
echo NOT: Xbox emulasyonu icin ViGEmBus, kolu gizlemek icin HidHide gerekir.
echo      Kurulum dosyalari tools\ klasorunde ^(yonetici izni ister^).
pause
