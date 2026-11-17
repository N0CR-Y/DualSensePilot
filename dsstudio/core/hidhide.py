"""HidHide entegrasyonu: fiziksel kolu oyunlardan gizlemek için (isteğe bağlı).

HidHide kuruluysa CLI aracı ile uygulamayı beyaz listeye alır ve kolun
cihaz örnek yolunu gizler. Bu işlemler yönetici hakkı ister (UAC sorar).
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

CLI_CANDIDATES = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Nefarius Software Solutions" / "HidHide" / "x64" / "HidHideCLI.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Nefarius Software Solutions" / "HidHide" / "HidHideCLI.exe",
]


def cli_path() -> Path | None:
    for c in CLI_CANDIDATES:
        if c.exists():
            return c
    return None


def is_installed() -> bool:
    return cli_path() is not None


def own_executable() -> str:
    """Beyaz listeye alınacak çalıştırılabilir dosya.

    Dondurulmuş (PyInstaller) derlemede sys.executable uygulamanın kendi .exe'sidir.
    Geliştirme ortamında ise python.exe'dir (HidHide o durumda python.exe'yi
    beyaz listeye alır; kurulmuş sürümde gerçek uygulama exe'si eklenir).
    """
    return sys.executable


class _SHELLEXECUTEINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wt.HWND),
        ("lpVerb", wt.LPCWSTR),
        ("lpFile", wt.LPCWSTR),
        ("lpParameters", wt.LPCWSTR),
        ("lpDirectory", wt.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wt.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wt.LPCWSTR),
        ("hKeyClass", wt.HANDLE),
        ("dwHotKey", wt.DWORD),
        ("hIconOrMonitor", wt.HANDLE),
        ("hProcess", wt.HANDLE),
    ]


_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SW_HIDE = 0
_INFINITE = 0xFFFFFFFF


def _run_elevated_batch(commands: list[list[str]], timeout_ms: int = 15000) -> bool:
    """Komutları tek bir yükseltilmiş cmd oturumunda çalıştırır (tek UAC) ve
    gerçekten başarılı olup olmadığını (UAC onaylandı mı, komut 0 ile mi bitti)
    bekleyip döndürür.

    Komutlar, '&'in cmd.exe tarafında sorun çıkarabileceği (cihaz yollarında
    '&' karakteri sık görülür) `cmd /c "A" && "B"` birleştirmesi yerine, tek
    satır tek komut olacak şekilde geçici bir .bat dosyasına yazılır.
    """
    cli = cli_path()
    if cli is None:
        return False
    fd, path = tempfile.mkstemp(suffix=".bat", prefix="dsstudio_hh_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write("@echo off\r\n")
            for args in commands:
                quoted = " ".join(f'"{a}"' for a in args)
                fh.write(f'"{cli}" {quoted}\r\n')
                fh.write("if errorlevel 1 exit /b 1\r\n")

        sei = _SHELLEXECUTEINFO()
        sei.cbSize = ctypes.sizeof(sei)
        sei.fMask = _SEE_MASK_NOCLOSEPROCESS
        sei.lpVerb = "runas"
        sei.lpFile = "cmd.exe"
        sei.lpParameters = f'/c ""{path}""'
        sei.nShow = _SW_HIDE
        ok = ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(sei))
        if not ok or not sei.hProcess:
            # UAC reddedildi (ERROR_CANCELLED) veya başlatılamadı.
            return False
        try:
            ctypes.windll.kernel32.WaitForSingleObject(sei.hProcess, timeout_ms)
            exit_code = wt.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(sei.hProcess, ctypes.byref(exit_code))
            return exit_code.value == 0
        finally:
            ctypes.windll.kernel32.CloseHandle(sei.hProcess)
    except Exception as e:  # noqa: BLE001
        log.warning("yükseltilmiş HidHide komutu çalıştırılamadı: %s", e)
        return False
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def hide_device(instance_path: str) -> bool:
    return _run_elevated_batch([
        ["--app-reg", own_executable()],
        ["--dev-hide", instance_path],
        ["--cloak-on"],
    ])


def unhide_device(instance_path: str) -> bool:
    return _run_elevated_batch([
        ["--dev-unhide", instance_path],
    ])


def cloak_off() -> bool:
    return _run_elevated_batch([["--cloak-off"]])


def query_state() -> dict:
    """Mevcut durumu (yükseltme gerektirmeden) okumaya çalışır."""
    cli = cli_path()
    info = {"installed": cli is not None, "cloak": None, "devices": [], "apps": []}
    if cli is None:
        return info
    try:
        r = subprocess.run([str(cli), "--cloak-state"], capture_output=True, text=True, timeout=5,
                           creationflags=0x08000000)
        info["cloak"] = "on" in r.stdout.lower() and "off" not in r.stdout.lower()
        r = subprocess.run([str(cli), "--dev-list"], capture_output=True, text=True, timeout=5,
                           creationflags=0x08000000)
        info["devices"] = [l.strip() for l in r.stdout.splitlines() if l.strip()]
        r = subprocess.run([str(cli), "--app-list"], capture_output=True, text=True, timeout=5,
                           creationflags=0x08000000)
        info["apps"] = [l.strip() for l in r.stdout.splitlines() if l.strip()]
    except Exception:  # noqa: BLE001
        pass
    return info
