from __future__ import annotations

import os
import threading
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QRadioButton)

from ...core import hidhide
from ...core.emulator import vigem_available
from ..widgets import Badge, Card, LabeledSlider
from .base import PageBase

TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools"


class EmulationPage(PageBase):
    title = "Emülasyon"
    subtitle = ("Kolu oyunlara Xbox 360 ya da DualShock 4 olarak tanıt. "
                "Xbox 360 modu neredeyse her PC oyununda çalışır.")

    # HidHide sorguları ve UAC gerektiren komutlar ayrı iş parçacıklarında
    # çalışır; sonuçlar bu sinyallerle Qt ana iş parçacığına güvenle taşınır.
    _hidhide_state_ready = Signal(dict)
    _hidhide_action_done = Signal(str, bool, str)

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        em = Card("Sanal kol")
        srow = QHBoxLayout()
        srow.addWidget(QLabel("ViGEmBus sürücüsü"))
        self.badge_vigem = Badge("kontrol ediliyor", "info")
        srow.addWidget(self.badge_vigem)
        srow.addStretch(1)
        em.add_layout(srow)
        self.group = QButtonGroup(self)
        self.radios = {}
        for key, label in [("x360", "Xbox 360 kolu (önerilen)"), ("ds4", "DualShock 4 (PS4 kolu)"), ("none", "Emülasyon yok (yalnızca ışık/tetik)")]:
            r = QRadioButton(label)
            self.group.addButton(r)
            self.radios[key] = r
            r.toggled.connect(lambda on, k=key: on and self._kind_changed(k))
            em.add(r)
        brow = QHBoxLayout()
        self.btn_toggle = QPushButton("Başlat")
        self.btn_toggle.setObjectName("primary")
        self.btn_toggle.clicked.connect(self._toggle)
        self.badge_state = Badge("Kapalı", "off")
        brow.addWidget(self.btn_toggle)
        brow.addWidget(self.badge_state)
        brow.addStretch(1)
        em.add_layout(brow)
        self.cb_auto = QCheckBox("Kol bağlanınca emülasyonu otomatik başlat")
        self.cb_auto.toggled.connect(self._auto_changed)
        em.add(self.cb_auto)
        warn = QLabel("Çift giriş uyarısı: Oyun hem gerçek DualSense'i hem sanal kolu görürse tuşlar iki kez algılanabilir. "
                      "Bunu önlemek için HidHide ile gerçek kolu gizle (sağdaki kart) ya da Steam'de PlayStation kol desteğini kapat.")
        warn.setObjectName("muted")
        warn.setWordWrap(True)
        em.add(warn)
        row.addWidget(em, 1)

        opt = Card("Eşleme ayarları")
        self.sl_dz = LabeledSlider("Çubuk ölü bölgesi", 0, 40, 5, "%")
        self.sl_dz.valueChanged.connect(lambda v: self._set("stick_deadzone", v))
        opt.add(self.sl_dz)
        self.sl_thr = LabeledSlider("Tetik eşiği", 0, 200, 0)
        self.sl_thr.setToolTip("Bu değerin altındaki tetik basıncı yok sayılır.")
        self.sl_thr.valueChanged.connect(lambda v: self._set("trigger_threshold", v))
        opt.add(self.sl_thr)
        self.cb_inv_l = QCheckBox("Sol çubuk Y eksenini ters çevir")
        self.cb_inv_r = QCheckBox("Sağ çubuk Y eksenini ters çevir")
        self.cb_swap = QCheckBox("Çubukları değiştir (sol ↔ sağ)")
        self.cb_touch = QCheckBox("Dokunmatik yüzey tıklaması = Back/Share")
        for cb, key in [(self.cb_inv_l, "invert_left_y"), (self.cb_inv_r, "invert_right_y"),
                        (self.cb_swap, "swap_sticks"), (self.cb_touch, "touchpad_as_back")]:
            cb.toggled.connect(lambda on, k=key: self._set(k, on))
            opt.add(cb)
        map_info = QLabel("Xbox 360 eşlemesi: ✕=A  ○=B  □=X  △=Y  L1/R1=LB/RB  L2/R2=LT/RT  "
                          "Create=Back  Options=Start  PS=Guide")
        map_info.setObjectName("muted")
        map_info.setWordWrap(True)
        opt.add(map_info)
        row.addWidget(opt, 1)
        self.content.addLayout(row)

        hh = Card("HidHide (gerçek kolu oyunlardan gizle)")
        hrow = QHBoxLayout()
        hrow.addWidget(QLabel("Durum"))
        self.badge_hh = Badge("-", "info")
        hrow.addWidget(self.badge_hh)
        hrow.addStretch(1)
        hh.add_layout(hrow)
        bh = QHBoxLayout()
        self.btn_hide = QPushButton("Kolu gizle (UAC ister)")
        self.btn_hide.clicked.connect(self._hide)
        self.btn_unhide = QPushButton("Gizlemeyi kaldır")
        self.btn_unhide.clicked.connect(self._unhide)
        self.btn_install_hh = QPushButton("HidHide kur…")
        self.btn_install_hh.clicked.connect(lambda: self._open_installer("HidHide"))
        self.btn_install_vigem = QPushButton("ViGEmBus 1.22 kur/güncelle…")
        self.btn_install_vigem.clicked.connect(lambda: self._open_installer("ViGEmBus"))
        for b in (self.btn_hide, self.btn_unhide, self.btn_install_hh, self.btn_install_vigem):
            bh.addWidget(b)
        bh.addStretch(1)
        hh.add_layout(bh)
        hh_note = QLabel("HidHide, bu uygulamayı beyaz listeye alıp DualSense'i diğer programlardan saklar. "
                         "Böylece oyun yalnızca sanal Xbox kolunu görür. Kurulumdan sonra bilgisayarı yeniden başlatman gerekebilir.")
        hh_note.setObjectName("muted")
        hh_note.setWordWrap(True)
        hh.add(hh_note)
        self.content.addWidget(hh)

        self.service.emulation_changed.connect(self._on_emu_changed)
        self.service.device_connected.connect(lambda _: self._refresh_hidhide())
        self._hidhide_state_ready.connect(self._apply_hidhide_state)
        self._hidhide_action_done.connect(self._on_hidhide_action_done)
        self._hh_query_running = False
        self._refresh_vigem()
        self._refresh_hidhide()

    # ------------------------------------------------------------------
    def refresh(self):
        self._loading = True
        p = self.profile
        (self.radios.get(p.emulation) or self.radios["x360"]).setChecked(True)
        self.sl_dz.setValue(p.stick_deadzone)
        self.sl_thr.setValue(p.trigger_threshold)
        self.cb_inv_l.setChecked(p.invert_left_y)
        self.cb_inv_r.setChecked(p.invert_right_y)
        self.cb_swap.setChecked(p.swap_sticks)
        self.cb_touch.setChecked(p.touchpad_as_back)
        self.cb_auto.setChecked(self.service.store.settings.auto_emulation)
        self._loading = False
        self._on_emu_changed(self.service.emulator.kind)

    def _refresh_vigem(self):
        ok, err = vigem_available()
        if ok:
            self.badge_vigem.setText("Kurulu ve hazır")
            self.badge_vigem.setKind("ok")
        else:
            self.badge_vigem.setText("Bulunamadı")
            self.badge_vigem.setKind("off")
            self.badge_vigem.setToolTip(err)

    def _refresh_hidhide(self):
        if not hidhide.is_installed():
            self.badge_hh.setText("Kurulu değil")
            self.badge_hh.setKind("off")
            self.btn_hide.setEnabled(False)
            self.btn_unhide.setEnabled(False)
            return
        if self._hh_query_running:
            return
        self._hh_query_running = True
        self.badge_hh.setText("Kontrol ediliyor…")
        self.badge_hh.setKind("info")

        def _worker():
            try:
                st = hidhide.query_state()
            except Exception:  # noqa: BLE001
                st = {"installed": True, "cloak": None}
            self._hidhide_state_ready.emit(st)

        threading.Thread(target=_worker, daemon=True, name="hidhide-query").start()

    def _apply_hidhide_state(self, st: dict):
        self._hh_query_running = False
        txt = "Kurulu"
        if st.get("cloak") is True:
            txt += " · gizleme açık"
        elif st.get("cloak") is False:
            txt += " · gizleme kapalı"
        self.badge_hh.setText(txt)
        self.badge_hh.setKind("ok")
        self.btn_hide.setEnabled(True)
        self.btn_unhide.setEnabled(True)

    def _kind_changed(self, kind):
        if self._loading:
            return
        self.service.set_profile_attr("emulation", kind)
        if self.service.connected and self.service.store.settings.auto_emulation:
            self.service.start_emulation(kind)

    def _toggle(self):
        if self.service.emulator.active:
            self.service.stop_emulation()
        else:
            kind = self.profile.emulation if self.profile.emulation != "none" else "x360"
            if not self.service.connected:
                QMessageBox.information(self, "Kol bağlı değil", "Önce DualSense'i bağla (USB ya da Bluetooth).")
                return
            self.service.start_emulation(kind)

    def _on_emu_changed(self, kind):
        if kind == "none":
            self.badge_state.setText("Kapalı")
            self.badge_state.setKind("off")
            self.btn_toggle.setText("Başlat")
        else:
            self.badge_state.setText("Aktif: " + ("Xbox 360" if kind == "x360" else "DualShock 4"))
            self.badge_state.setKind("ok")
            self.btn_toggle.setText("Durdur")

    def _auto_changed(self, on):
        if self._loading:
            return
        self.service.store.settings.auto_emulation = on
        self.service.store.save_settings()

    def _set(self, key, value):
        if self._loading:
            return
        # Bu alanlar (deadzone, eşik, ters çevirme, çubuk değiştirme...) HID okuma
        # iş parçacığındaki Emulator.feed() tarafından okunuyor; thread-safe setter
        # kullan (bkz. ControllerService.set_profile_attr).
        self.service.set_profile_attr(key, value)
        self.service.update_outputs()

    def _hide(self):
        dev = self.service.device
        if dev is None:
            QMessageBox.information(self, "Kol bağlı değil", "Gizlemek için önce kolu bağla.")
            return
        path = dev.info.instance_path
        self.btn_hide.setEnabled(False)
        self.btn_unhide.setEnabled(False)

        def _worker():
            ok = hidhide.hide_device(path)
            self._hidhide_action_done.emit("hide", ok, path)

        threading.Thread(target=_worker, daemon=True, name="hidhide-hide").start()

    def _unhide(self):
        dev = self.service.device
        path = dev.info.instance_path if dev is not None else ""
        self.btn_hide.setEnabled(False)
        self.btn_unhide.setEnabled(False)

        def _worker():
            ok = hidhide.unhide_device(path) if path else hidhide.cloak_off()
            self._hidhide_action_done.emit("unhide", ok, path)

        threading.Thread(target=_worker, daemon=True, name="hidhide-unhide").start()

    def _on_hidhide_action_done(self, action: str, ok: bool, path: str):
        if action == "hide":
            if ok:
                QMessageBox.information(self, "HidHide",
                                         f"Kol gizlendi:\n{path}\n\nUygulama beyaz listeye alındı ve gizleme açıldı.")
            else:
                QMessageBox.warning(self, "HidHide", "Komut başarısız oldu (UAC reddedildi ya da HidHideCLI hata verdi).")
        else:
            if not ok:
                QMessageBox.warning(self, "HidHide", "Gizleme kaldırma komutu başarısız oldu (UAC reddedildi olabilir).")
        self._refresh_hidhide()

    def _open_installer(self, which: str):
        if not TOOLS_DIR.exists():
            QMessageBox.warning(self, "Bulunamadı", f"'tools' klasörü yok: {TOOLS_DIR}")
            return
        cands = sorted(TOOLS_DIR.glob(f"{which}*.exe"))
        if not cands:
            QMessageBox.warning(self, "Bulunamadı", f"{which} kurulum dosyası tools klasöründe yok.")
            return
        os.startfile(str(cands[-1]))
