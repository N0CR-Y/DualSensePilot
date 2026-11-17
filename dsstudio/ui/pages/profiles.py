from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QApplication, QCheckBox, QHBoxLayout, QInputDialog, QLabel, QListWidget,
                               QMessageBox, QPushButton, QVBoxLayout, QComboBox, QDialog, QDialogButtonBox)

from ...core.foreground import running_process_names
from ...core.profiles import Profile
from ..widgets import Card
from .base import PageBase


class ProfilesPage(PageBase):
    title = "Profiller"
    subtitle = ("Ayar setlerini profil olarak kaydet. Bir profile oyun exe'si bağlarsan oyun öne geçtiğinde "
                "otomatik olarak o profil uygulanır.")

    # "tasklist" çağrısı (~birkaç yüz ms, bazen daha uzun) UI thread'ini
    # dondurmasın diye arka planda çalışır; sonuç bu sinyalle geri döner.
    _running_names_ready = Signal(list)

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        lst = Card("Profiller")
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        self.list.itemDoubleClicked.connect(lambda _: self._activate())
        lst.add(self.list)
        b1 = QHBoxLayout()
        self.btn_activate = QPushButton("Etkinleştir")
        self.btn_activate.setObjectName("primary")
        self.btn_activate.clicked.connect(self._activate)
        self.btn_save = QPushButton("Mevcut ayarları kaydet")
        self.btn_save.clicked.connect(self._save_current)
        b1.addWidget(self.btn_activate)
        b1.addWidget(self.btn_save)
        b1.addStretch(1)
        lst.add_layout(b1)
        b2 = QHBoxLayout()
        for label, fn in [("Yeni", self._new), ("Kopyala", self._duplicate), ("Yeniden adlandır", self._rename), ("Sil", self._delete)]:
            b = QPushButton(label)
            if label == "Sil":
                b.setObjectName("danger")
            b.clicked.connect(fn)
            b2.addWidget(b)
        b2.addStretch(1)
        lst.add_layout(b2)
        self.lbl_active = QLabel("")
        self.lbl_active.setObjectName("muted")
        lst.add(self.lbl_active)
        row.addWidget(lst, 1)

        auto = Card("Otomatik profil (oyuna göre)")
        self.cb_auto = QCheckBox("Ön plandaki uygulamaya göre profili otomatik değiştir")
        self.cb_auto.toggled.connect(self._auto_toggled)
        auto.add(self.cb_auto)
        auto.add(QLabel("Seçili profile bağlı uygulamalar (exe adı):"))
        self.exe_list = QListWidget()
        self.exe_list.setMinimumHeight(160)
        auto.add(self.exe_list)
        b3 = QHBoxLayout()
        ba = QPushButton("Çalışan uygulamadan ekle")
        ba.clicked.connect(self._add_running)
        bm = QPushButton("Elle ekle")
        bm.clicked.connect(self._add_manual)
        br = QPushButton("Kaldır")
        br.clicked.connect(self._remove_exe)
        b3.addWidget(ba)
        b3.addWidget(bm)
        b3.addWidget(br)
        b3.addStretch(1)
        auto.add_layout(b3)
        note = QLabel("Örnek: 'eldenring.exe', 'cs2.exe'. Oyun kapanınca elle seçtiğin profile geri dönülür.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        auto.add(note)
        row.addWidget(auto, 1)
        self.content.addLayout(row)

        self.list.currentItemChanged.connect(lambda *_: self._load_exe_list())
        self.service.profile_changed.connect(lambda _: self._reload_list())
        self._running_names_ready.connect(self._show_running_dialog)
        self._running_query_active = False
        self._reload_list()

    # ------------------------------------------------------------------
    def refresh(self):
        self._reload_list()
        self.cb_auto.setChecked(self.service.store.settings.auto_switch)

    def _reload_list(self):
        cur = self._selected_name()
        self.list.blockSignals(True)
        self.list.clear()
        for name in self.service.store.profiles:
            self.list.addItem(name)
        target = cur or self.service.profile.name
        items = self.list.findItems(target, Qt.MatchExactly)
        if items:
            self.list.setCurrentItem(items[0])
        elif self.list.count():
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self.lbl_active.setText(f"Etkin profil: {self.service.profile.name}")
        self._load_exe_list()

    def _selected_name(self) -> str | None:
        it = self.list.currentItem()
        return it.text() if it else None

    def _selected_profile(self) -> Profile | None:
        n = self._selected_name()
        return self.service.store.get(n) if n else None

    def _activate(self):
        p = self._selected_profile()
        if p is None:
            return
        self.service.apply_profile(p.clone())
        self.window().statusBar().showMessage(f"Profil etkinleştirildi: {p.name}", 3000)

    def _save_current(self):
        p = self.service.profile
        self.service.store.save_profile(p.clone())
        self.service.store.settings.active_profile = p.name
        self.service.store.save_settings()
        self._reload_list()
        self.window().statusBar().showMessage(f"Kaydedildi: {p.name}", 3000)

    def _new(self):
        name, ok = QInputDialog.getText(self, "Yeni profil", "Profil adı:")
        name = (name or "").strip()
        if not ok or not name:
            return
        if name in self.service.store.profiles:
            QMessageBox.warning(self, "Profil", "Bu adda bir profil zaten var.")
            return
        p = Profile(name=name)
        self.service.store.save_profile(p)
        self.service.apply_profile(p.clone())
        self._reload_list()

    def _duplicate(self):
        src = self._selected_profile()
        if src is None:
            return
        name, ok = QInputDialog.getText(self, "Profili kopyala", "Yeni ad:", text=src.name + " (kopya)")
        name = (name or "").strip()
        if not ok or not name or name in self.service.store.profiles:
            return
        p = src.clone()
        p.name = name
        self.service.store.save_profile(p)
        self._reload_list()

    def _rename(self):
        src = self._selected_profile()
        if src is None:
            return
        name, ok = QInputDialog.getText(self, "Yeniden adlandır", "Yeni ad:", text=src.name)
        name = (name or "").strip()
        if not ok or not name or name == src.name or name in self.service.store.profiles:
            return
        old = src.name
        p = src.clone()
        p.name = name
        self.service.store.save_profile(p, old_name=old)
        if self.service.profile.name == old:
            self.service.profile.name = name
            self.service.store.settings.active_profile = name
            self.service.store.save_settings()
        self._reload_list()

    def _delete(self):
        src = self._selected_profile()
        if src is None:
            return
        if QMessageBox.question(self, "Sil", f"'{src.name}' profili silinsin mi?") != QMessageBox.Yes:
            return
        self.service.store.delete_profile(src.name)
        if self.service.profile.name == src.name:
            self.service.apply_profile(self.service.store.active.clone())
        self._reload_list()

    # -- exe listesi -----------------------------------------------------
    def _load_exe_list(self):
        self.exe_list.clear()
        p = self._selected_profile()
        if p:
            for n in p.exe_names:
                self.exe_list.addItem(n)

    def _add_exe(self, name: str):
        name = (name or "").strip()
        p = self._selected_profile()
        if not name or p is None:
            return
        if not name.lower().endswith(".exe"):
            name += ".exe"
        if name.lower() in [n.lower() for n in p.exe_names]:
            return
        p.exe_names.append(name)
        self.service.store.save_profile(p)
        if self.service.profile.name == p.name:
            self.service.profile.exe_names = list(p.exe_names)
        self._load_exe_list()

    def _add_manual(self):
        name, ok = QInputDialog.getText(self, "Uygulama ekle", "Exe adı (ör. oyun.exe):")
        if ok:
            self._add_exe(name)

    def _add_running(self):
        if self._running_query_active:
            return
        self._running_query_active = True
        QApplication.setOverrideCursor(Qt.WaitCursor)

        def _worker():
            try:
                names = running_process_names()
            except Exception:  # noqa: BLE001
                names = []
            self._running_names_ready.emit(names)

        threading.Thread(target=_worker, daemon=True, name="proc-list").start()

    def _show_running_dialog(self, names):
        self._running_query_active = False
        QApplication.restoreOverrideCursor()
        if not names:
            QMessageBox.information(self, "Uygulama", "Çalışan uygulama listesi alınamadı.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Çalışan uygulamadan ekle")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Önce oyunu başlat, sonra listeden seç:"))
        cb = QComboBox()
        cb.setEditable(True)
        cb.addItems(names)
        lay.addWidget(cb)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() == QDialog.Accepted:
            self._add_exe(cb.currentText())

    def _remove_exe(self):
        it = self.exe_list.currentItem()
        p = self._selected_profile()
        if it is None or p is None:
            return
        p.exe_names = [n for n in p.exe_names if n != it.text()]
        self.service.store.save_profile(p)
        if self.service.profile.name == p.name:
            self.service.profile.exe_names = list(p.exe_names)
        self._load_exe_list()

    def _auto_toggled(self, on):
        self.service.store.settings.auto_switch = on
        self.service.store.save_settings()
