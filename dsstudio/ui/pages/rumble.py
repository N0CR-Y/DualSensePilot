from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QProgressBar, QPushButton

from ..widgets import Card, LabeledSlider
from .base import PageBase


class RumblePage(PageBase):
    title = "Titreşim"
    subtitle = "Motorları test et ve oyunlardan gelen titreşimin kola nasıl aktarılacağını ayarla."

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        test = Card("Motor testi")
        self.sl_left = LabeledSlider("Sol motor (güçlü)", 0, 255, 180)
        self.sl_right = LabeledSlider("Sağ motor (hafif)", 0, 255, 120)
        test.add(self.sl_left)
        test.add(self.sl_right)
        brow = QHBoxLayout()
        b1 = QPushButton("Kısa test (0.6 s)")
        b1.setObjectName("primary")
        b1.clicked.connect(lambda: self.service.test_rumble(self.sl_left.value(), self.sl_right.value(), 600))
        b2 = QPushButton("Uzun test (3 s)")
        b2.clicked.connect(lambda: self.service.test_rumble(self.sl_left.value(), self.sl_right.value(), 3000))
        b3 = QPushButton("Durdur")
        b3.clicked.connect(self.service.stop_rumble)
        brow.addWidget(b1)
        brow.addWidget(b2)
        brow.addWidget(b3)
        brow.addStretch(1)
        test.add_layout(brow)
        self.cb_live = QCheckBox("Kaydırıcıyı sürüklerken canlı titreştir")
        test.add(self.cb_live)
        self.sl_left.valueChanged.connect(self._live)
        self.sl_right.valueChanged.connect(self._live)
        row.addWidget(test, 1)

        game = Card("Oyun titreşimi (sanal koldan aktarım)")
        self.cb_pass = QCheckBox("Oyundan gelen titreşimi kola aktar")
        self.cb_pass.toggled.connect(self._pass_changed)
        game.add(self.cb_pass)
        self.sl_scale = LabeledSlider("Şiddet", 0, 200, 100, "%")
        self.sl_scale.valueChanged.connect(self._scale_changed)
        game.add(self.sl_scale)
        self.sl_min = LabeledSlider("Alt eşik", 0, 255, 0)
        self.sl_min.setToolTip("Sıfırdan büyük her titreşim en az bu değerde olur (zayıf titreşimleri hissedilir yapar).")
        self.sl_min.valueChanged.connect(self._min_changed)
        game.add(self.sl_min)
        game.add(QLabel("Oyundan gelen son değerler"))
        self.bar_l = QProgressBar(); self.bar_l.setRange(0, 255); self.bar_l.setObjectName("rumble"); self.bar_l.setFormat("Sol %v")
        self.bar_r = QProgressBar(); self.bar_r.setRange(0, 255); self.bar_r.setObjectName("rumble"); self.bar_r.setFormat("Sağ %v")
        game.add(self.bar_l)
        game.add(self.bar_r)
        note = QLabel("Not: Titreşim yalnızca emülasyon (Xbox 360 / DS4) açıkken oyundan gelir. "
                      "Yeni yazılımlı kollarda 'gelişmiş titreşim' (v2) otomatik kullanılır.")
        note.setObjectName("muted")
        note.setWordWrap(True)
        game.add(note)
        row.addWidget(game, 1)
        self.content.addLayout(row)
        self.service.rumble_received.connect(self._on_rumble)

    def refresh(self):
        self._loading = True
        p = self.profile
        self.cb_pass.setChecked(p.rumble_passthrough)
        self.sl_scale.setValue(p.rumble_scale)
        self.sl_min.setValue(p.rumble_min)
        self._loading = False

    def _live(self, *_):
        if self.cb_live.isChecked():
            self.service.test_rumble(self.sl_left.value(), self.sl_right.value(), 400)

    def _pass_changed(self, on):
        if self._loading:
            return
        self.profile.rumble_passthrough = on
        self.service.update_outputs()

    def _scale_changed(self, v):
        if self._loading:
            return
        self.profile.rumble_scale = v

    def _min_changed(self, v):
        if self._loading:
            return
        self.profile.rumble_min = v

    def _on_rumble(self, l, r):
        self.bar_l.setValue(l)
        self.bar_r.setValue(r)
