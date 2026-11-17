from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QComboBox, QFrame, QHBoxLayout, QLabel, QProgressBar, QPushButton,
                               QVBoxLayout, QWidget, QGridLayout)

from ...core import triggers as T
from ...core.profiles import TriggerConfig
from ..widgets import Card, LabeledSlider
from .base import PageBase


class TriggerPanel(Card):
    changed = Signal(str, dict)   # mode, params
    copy_requested = Signal()

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self._loading = False
        self.mode = "off"
        self.params: dict = {}
        self._sliders: dict[str, LabeledSlider] = {}
        self._array_sliders: list[LabeledSlider] = []

        top = QHBoxLayout()
        top.addWidget(QLabel("Hazır ayar"))
        self.cb_preset = QComboBox()
        self.cb_preset.addItem("Seç…")
        for name, _, _ in T.PRESETS:
            self.cb_preset.addItem(name)
        self.cb_preset.currentIndexChanged.connect(self._preset_selected)
        top.addWidget(self.cb_preset, 1)
        self.add_layout(top)

        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Mod"))
        self.cb_mode = QComboBox()
        for key, spec in T.MODES.items():
            self.cb_mode.addItem(spec.label, key)
        self.cb_mode.currentIndexChanged.connect(self._mode_selected)
        mrow.addWidget(self.cb_mode, 1)
        self.add_layout(mrow)

        self.lbl_desc = QLabel("")
        self.lbl_desc.setObjectName("muted")
        self.lbl_desc.setWordWrap(True)
        self.add(self.lbl_desc)

        self.params_box = QWidget()
        self.params_layout = QVBoxLayout(self.params_box)
        self.params_layout.setContentsMargins(0, 0, 0, 0)
        self.params_layout.setSpacing(6)
        self.add(self.params_box)

        live = QHBoxLayout()
        live.addWidget(QLabel("Tetik değeri"))
        self.bar = QProgressBar()
        self.bar.setRange(0, 255)
        self.bar.setObjectName("rumble")
        self.bar.setFormat("%v")
        live.addWidget(self.bar, 1)
        self.lbl_fb = QLabel("")
        self.lbl_fb.setObjectName("muted")
        live.addWidget(self.lbl_fb)
        self.add_layout(live)

        brow = QHBoxLayout()
        self.btn_copy = QPushButton("Diğer tetiğe kopyala")
        self.btn_copy.clicked.connect(self.copy_requested.emit)
        brow.addWidget(self.btn_copy)
        brow.addStretch(1)
        self.add_layout(brow)

    # -- durum -----------------------------------------------------------
    def set_config(self, mode: str, params: dict):
        self._loading = True
        self.mode = mode if mode in T.MODES else "off"
        self.params = dict(params or {})
        idx = self.cb_mode.findData(self.mode)
        self.cb_mode.setCurrentIndex(max(0, idx))
        self._rebuild_params()
        self.cb_preset.setCurrentIndex(0)
        self._loading = False

    def _mode_selected(self, idx):
        if self._loading:
            return
        key = self.cb_mode.itemData(idx)
        if key == self.mode:
            return
        self.mode = key
        spec = T.MODES[key]
        self.params = {ps.key: ps.default for ps in spec.params}
        if spec.array_param:
            self.params[spec.array_param] = ([5] + [0] * 10) if key == "raw" else [0] * 10
        self._loading = True
        self._rebuild_params()
        self._loading = False
        self._emit()

    def _preset_selected(self, idx):
        if self._loading or idx <= 0:
            return
        name, mode, params = T.PRESETS[idx - 1]
        self._loading = True
        self.mode = mode
        self.params = dict(params)
        self.cb_mode.setCurrentIndex(max(0, self.cb_mode.findData(mode)))
        self._rebuild_params()
        self._loading = False
        self._emit()

    def _rebuild_params(self):
        while self.params_layout.count():
            item = self.params_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._sliders.clear()
        self._array_sliders.clear()
        spec = T.MODES[self.mode]
        self.lbl_desc.setText(spec.description)
        for ps in spec.params:
            val = self.params.get(ps.key, ps.default)
            s = LabeledSlider(ps.label, ps.min, ps.max, int(val), ps.unit)
            s.valueChanged.connect(lambda v, k=ps.key: self._param_changed(k, v))
            self._sliders[ps.key] = s
            self.params_layout.addWidget(s)
            self.params.setdefault(ps.key, ps.default)
        if spec.array_param:
            lab = QLabel(spec.array_label)
            lab.setObjectName("muted")
            self.params_layout.addWidget(lab)
            n = 11 if self.mode == "raw" else 10
            arr = list(self.params.get(spec.array_param) or [])
            arr = (arr + [0] * n)[:n]
            self.params[spec.array_param] = arr
            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            for i in range(n):
                label = f"Bayt {i}" if self.mode == "raw" else f"Bölge {i + 1}"
                s = LabeledSlider(label, 0, spec.array_max, int(arr[i]))
                s.label.setMinimumWidth(60)
                s.valueChanged.connect(lambda v, i=i: self._array_changed(i, v))
                self._array_sliders.append(s)
                grid.addWidget(s, i % 6, i // 6)
            self.params_layout.addLayout(grid)

    def _param_changed(self, key, v):
        if self._loading:
            return
        self.params[key] = v
        self._emit()

    def _array_changed(self, i, v):
        if self._loading:
            return
        spec = T.MODES[self.mode]
        arr = list(self.params.get(spec.array_param) or [])
        if i < len(arr):
            arr[i] = v
            self.params[spec.array_param] = arr
            self._emit()

    def _emit(self):
        self.changed.emit(self.mode, dict(self.params))

    def set_live(self, value: int, feedback: int):
        self.bar.setValue(value)
        self.lbl_fb.setText(f"durum 0x{feedback:02X}")


class TriggersPage(PageBase):
    title = "Adaptif tetikler"
    subtitle = ("L2 ve R2 için direnç, silah tetiği, titreşim gibi efektler. "
                "Değişiklikler anında kola uygulanır; kalıcı olması için profili kaydet.")

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        self.left = TriggerPanel("L2 (Sol tetik)")
        self.right = TriggerPanel("R2 (Sağ tetik)")
        self.left.changed.connect(lambda m, p: self._changed("left", m, p))
        self.right.changed.connect(lambda m, p: self._changed("right", m, p))
        self.left.copy_requested.connect(lambda: self._copy("left"))
        self.right.copy_requested.connect(lambda: self._copy("right"))
        row.addWidget(self.left, 1)
        row.addWidget(self.right, 1)
        self.content.addLayout(row)

        info = QLabel("İpucu: Konum değerleri 0-9 arasında tetik yolunu temsil eder (0 = en üst). "
                      "Kuvvet 0-8 arasıdır. Oyun kendi efektlerini gönderirse (DualSense destekli oyunlar, USB) "
                      "bu ayarlar oyunun ayarlarıyla çakışabilir.")
        info.setObjectName("muted")
        info.setWordWrap(True)
        self.content.addWidget(info)

    def refresh(self):
        p = self.profile
        self.left.set_config(p.left_trigger.mode, p.left_trigger.params)
        self.right.set_config(p.right_trigger.mode, p.right_trigger.params)

    def _changed(self, side, mode, params):
        self.service.set_trigger(side, mode, params)

    def _copy(self, src):
        p = self.profile
        s = p.left_trigger if src == "left" else p.right_trigger
        dst = "right" if src == "left" else "left"
        self.service.set_trigger(dst, s.mode, dict(s.params))
        panel = self.right if dst == "right" else self.left
        panel.set_config(s.mode, s.params)

    def update_live(self):
        s = self.service.last_state
        if s is None:
            return
        self.left.set_live(s.l2, s.l2_feedback)
        self.right.set_live(s.r2, s.r2_feedback)
