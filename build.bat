@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Once kur.bat calistir & pause & exit /b 1)

echo [1/3] Simge uretiliyor...
".venv\Scripts\python.exe" make_icon.py
if errorlevel 1 (echo Simge uretme hatasi & pause & exit /b 1)

echo [2/3] PyInstaller ile uygulama paketleniyor (dist\DualSensePilot)...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name DualSensePilot ^
  --icon assets\app.ico ^
  --collect-all vgamepad ^
  --collect-binaries hid ^
  --add-data "tools;tools" ^
  run.py
if errorlevel 1 (echo Derleme hatasi & pause & exit /b 1)

echo [3/3] Kurulum sihirbazi (Inno Setup) derleniyor...
set "ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (echo Inno Setup bulunamadi: winget install JRSoftware.InnoSetup & pause & exit /b 1)
"%ISCC%" installer.iss
if errorlevel 1 (echo Kurulum derleme hatasi & pause & exit /b 1)

echo.
echo Tamam: installer_out\DualSensePilot_Setup.exe
pause
