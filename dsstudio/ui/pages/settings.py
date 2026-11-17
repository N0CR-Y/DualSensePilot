from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton

from ... import APP_NAME, __version__
from ...core.profiles import APP_DIR
from ..widgets import Card
from .base import PageBase

STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
STARTUP_FILE = STARTUP_DIR / "DualSensePilot.cmd"


def _launch_command() -> str:
    if getattr(sys, "frozen", False):
        return f'start "" "{sys.executable}"'
    root = Path(__file__).resolve().parents[3]
    pyw = Path(sys.executable).with_name("pythonw.exe")
    exe = pyw if pyw.exists() else Path(sys.executable)
    return f'start "" "{exe}" "{root / "run.py"}" --minimized'


class SettingsPage(PageBase):
    title = "Ayarlar"
    subtitle = "Uygulama davranışı ve bilgi."

    def build(self):
        gen = Card("Genel")
        s = self.service.store.settings
        self.cb_tray = QCheckBox("Kapatınca sistem tepsisine küçült")
        self.cb_tray.setChecked(s.minimize_to_tray)
        self.cb_tray.toggled.connect(lambda on: self._set("minimize_to_tray", on))
        self.cb_min = QCheckBox("Küçültülmüş başlat")
        self.cb_min.setChecked(s.start_minimized)
        self.cb_min.toggled.connect(lambda on: self._set("start_minimized", on))
        self.cb_startup = QCheckBox("Windows ile başlat")
        self.cb_startup.setChecked(STARTUP_FILE.exists())
        self.cb_startup.toggled.connect(self._startup_toggled)
        for cb in (self.cb_tray, self.cb_min, self.cb_startup):
            gen.add(cb)
        row = QHBoxLayout()
        b = QPushButton("Profil klasörünü aç")
        b.clicked.connect(lambda: os.startfile(str(APP_DIR)))
        row.addWidget(b)
        row.addStretch(1)
        gen.add_layout(row)
        self.content.addWidget(gen)

        info = Card("Hakkında")
        try:
            import PySide6
            qt = PySide6.__version__
        except Exception:  # noqa: BLE001
            qt = "?"
        txt = QLabel(f"{APP_NAME} v{__version__}\n"
                     f"Python {sys.version.split()[0]} · PySide6 {qt}\n"
                     f"Ayar klasörü: {APP_DIR}\n\n"
                     "Protokol referansları: Linux hid-playstation, pydualsense, DS4Windows, Nielk1 TriggerEffectGenerator (MIT).\n"
                     "Sanal kol: Nefarius ViGEmBus + vgamepad. Cihaz gizleme: Nefarius HidHide.")
        txt.setObjectName("muted")
        txt.setWordWrap(True)
        info.add(txt)
        self.content.addWidget(info)

        logc = Card("Günlük")
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(500)
        self.log.setMinimumHeight(180)
        logc.add(self.log)
        self.content.addWidget(logc)
        self.service.log_message.connect(self.append_log)

    def append_log(self, msg: str):
        from datetime import datetime
        self.log.appendPlainText(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _set(self, key, val):
        setattr(self.service.store.settings, key, val)
        self.service.store.save_settings()

    def _startup_toggled(self, on):
        try:
            if on:
                STARTUP_DIR.mkdir(parents=True, exist_ok=True)
                STARTUP_FILE.write_text("@echo off\r\n" + _launch_command() + "\r\n", encoding="utf-8")
            else:
                STARTUP_FILE.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001
            self.append_log(f"Başlangıç ayarı değiştirilemedi: {e}")
