from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, QSize
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow, QMenu, QStackedWidget,
                               QSystemTrayIcon, QToolButton, QVBoxLayout, QWidget, QButtonGroup)

from .. import APP_NAME, __version__
from ..core.service import ControllerService
from . import theme
from .pages.emulation import EmulationPage
from .pages.light import LightPage
from .pages.profiles import ProfilesPage
from .pages.rumble import RumblePage
from .pages.settings import SettingsPage
from .pages.status import StatusPage
from .pages.triggers import TriggersPage
from .widgets import StatusStrip, make_app_icon


class MainWindow(QMainWindow):
    def __init__(self, service: ControllerService):
        super().__init__()
        self.service = service
        self.setWindowTitle(f"{APP_NAME}")
        self.setWindowIcon(make_app_icon())
        self.resize(1180, 760)
        self.setMinimumSize(1160, 640)
        self._quitting = False

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- üst çubuk: sol durum, orta menü, sağ profil
        top = QWidget()
        top.setObjectName("topbar")
        top.setFixedHeight(72)
        tl = QHBoxLayout(top)
        tl.setContentsMargins(20, 0, 20, 0)
        tl.setSpacing(0)

        self.status_strip = StatusStrip()
        left = QWidget()
        left.setFixedWidth(232)
        ll = QHBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.status_strip, 0, Qt.AlignVCenter)
        ll.addStretch(1)

        self.stack = QStackedWidget()
        self.pages = [
            ("Durum", StatusPage(service)),
            ("Işık ve LED", LightPage(service)),
            ("Adaptif tetikler", TriggersPage(service)),
            ("Titreşim", RumblePage(service)),
            ("Emülasyon", EmulationPage(service)),
            ("Profiller", ProfilesPage(service)),
            ("Ayarlar", SettingsPage(service)),
        ]
        navw = QWidget()
        nl = QHBoxLayout(navw)
        nl.setContentsMargins(0, 0, 0, 0)
        nl.setSpacing(2)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for i, (name, page) in enumerate(self.pages):
            b = QToolButton()
            b.setObjectName("nav")
            b.setText(name)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolButtonStyle(Qt.ToolButtonTextOnly)
            b.setMinimumWidth(b.fontMetrics().horizontalAdvance(name) + 30)
            b.clicked.connect(lambda _=False, idx=i: self.stack.setCurrentIndex(idx))
            self.nav_group.addButton(b, i)
            nl.addWidget(b)
            self.stack.addWidget(page)
        self.nav_group.button(0).setChecked(True)

        right = QWidget()
        right.setFixedWidth(232)
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(2)
        rl.addStretch(1)
        self.lbl_profile = QLabel("")
        self.lbl_profile.setObjectName("topProfile")
        self.lbl_profile.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_emu = QLabel("")
        self.lbl_emu.setObjectName("topEmu")
        self.lbl_emu.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        rl.addWidget(self.lbl_profile)
        rl.addWidget(self.lbl_emu)
        rl.addStretch(1)

        tl.addWidget(left)
        tl.addStretch(1)
        tl.addWidget(navw)
        tl.addStretch(1)
        tl.addWidget(right)

        outer.addWidget(top)
        outer.addWidget(self.stack, 1)
        self.statusBar().showMessage("Hazır")
        self._kind = ""
        # --- tepsi
        self.tray = QSystemTrayIcon(make_app_icon(), self)
        menu = QMenu()
        a_show = QAction("Göster", self)
        a_show.triggered.connect(self.show_normal)
        a_quit = QAction("Çıkış", self)
        a_quit.triggered.connect(self.quit_app)
        self.tray_profiles = QMenu("Profil", menu)
        menu.addAction(a_show)
        menu.addMenu(self.tray_profiles)
        menu.addSeparator()
        menu.addAction(a_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(lambda r: self.show_normal() if r == QSystemTrayIcon.Trigger else None)
        self.tray.setToolTip(APP_NAME)
        self.tray.show()
        self._rebuild_tray_profiles()

        # --- sinyaller
        service.device_connected.connect(self._on_connected)
        service.device_disconnected.connect(self._on_disconnected)
        service.profile_changed.connect(self._on_profile_changed)
        service.log_message.connect(lambda m: self.statusBar().showMessage(m, 5000))
        service.auto_profile_changed.connect(self._on_auto_profile)
        service.emulation_changed.connect(self._on_emulation)

        self.live_timer = QTimer(self)
        self.live_timer.setInterval(33)
        self.live_timer.timeout.connect(self._live)
        self.live_timer.start()

        for _, page in self.pages:
            page.refresh()
        self._on_profile_changed(service.profile.name)

    # ------------------------------------------------------------------
    def _live(self):
        if self.isVisible():
            page = self.stack.currentWidget()
            if page is not None:
                page.update_live()
        s = self.service.last_state
        dev = self.service.device
        if s is not None and self.service.connected:
            kind = "Bluetooth" if (dev is not None and dev.is_bluetooth) else "USB"
            self.status_strip.set_status(True, kind, s.battery_percent, s.charging, s.battery_full, s.battery_error)
            info = "şarj oluyor" if s.charging else ("şarj oldu" if s.battery_full else "pil ile")
            self.tray.setToolTip(f"{APP_NAME} · {kind} · Pil %{s.battery_percent} ({info})")
        else:
            self.status_strip.set_status(False, "", 0, False, False, False)

    def _on_connected(self, label):
        self.tray.showMessage(APP_NAME, f"Kol bağlandı: {label}", QSystemTrayIcon.Information, 2500)

    def _on_disconnected(self, reason):
        self.status_strip.set_status(False, "", 0, False, False, False)
        self.tray.setToolTip(APP_NAME)

    def _on_emulation(self, kind):
        names = {"x360": "Xbox 360 emülasyonu açık", "ds4": "DualShock 4 emülasyonu açık"}
        self.lbl_emu.setText(names.get(kind, "Emülasyon kapalı"))

    def _on_profile_changed(self, name):
        self.lbl_profile.setText(f"Profil: {name}")
        self._on_emulation(self.service.emulator.kind)
        self.setWindowTitle(f"{APP_NAME} — {name}")
        for _, page in self.pages:
            page.refresh()
        self._rebuild_tray_profiles()

    def _on_auto_profile(self, name):
        if name:
            self.tray.showMessage(APP_NAME, f"Otomatik profil: {name}", QSystemTrayIcon.Information, 2000)

    def _rebuild_tray_profiles(self):
        self.tray_profiles.clear()
        for name in self.service.store.profiles:
            a = QAction(name, self)
            a.setCheckable(True)
            a.setChecked(name == self.service.profile.name)
            a.triggered.connect(lambda _=False, n=name: self._tray_pick(n))
            self.tray_profiles.addAction(a)

    def _tray_pick(self, name):
        p = self.service.store.get(name)
        if p:
            self.service.apply_profile(p.clone())

    def show_normal(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self):
        self._quitting = True
        self.close()
        QApplication.instance().quit()

    def closeEvent(self, ev):
        if not self._quitting and self.service.store.settings.minimize_to_tray and self.tray.isVisible():
            ev.ignore()
            self.hide()
            self.tray.showMessage(APP_NAME, "Arka planda çalışmaya devam ediyor. Çıkmak için tepsi simgesine sağ tıkla.",
                                  QSystemTrayIcon.Information, 2000)
            return
        try:
            self.service.store.settings.window_geometry = bytes(self.saveGeometry().toBase64()).decode()
            self.service.store.save_settings()
        except Exception:  # noqa: BLE001
            pass
        self.service.shutdown()
        ev.accept()



