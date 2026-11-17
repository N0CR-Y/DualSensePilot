"""Ön plandaki pencerenin işlem (exe) adını döner (otomatik profil için)."""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def foreground_exe() -> str:
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return ""
        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""
        h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wt.DWORD(1024)
            if _kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return os.path.basename(buf.value)
        finally:
            _kernel32.CloseHandle(h)
    except Exception:  # noqa: BLE001
        pass
    return ""


def running_process_names(limit: int = 300) -> list[str]:
    """Çalışan işlemlerin exe adlarını (benzersiz, sıralı) döner."""
    try:
        import subprocess
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
            creationflags=0x08000000, timeout=5,
        ).stdout
        names = set()
        for line in out.splitlines():
            if line.startswith('"'):
                name = line.split('","')[0].strip('"')
                if name.lower().endswith(".exe"):
                    names.add(name)
        return sorted(names, key=str.lower)[:limit]
    except Exception:  # noqa: BLE001
        return []
