from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QRadioButton, QWidget)

from ...core import protocol as P
from ..widgets import Card, ColorButton, LabeledSlider, Swatch
from .base import PageBase

PRESET_COLORS = [
    "#0066ff", "#00c8ff", "#00e676", "#ffea00", "#ff9100", "#ff1744",
    "#d500f9", "#ff4081", "#ffffff", "#8d6e63", "#00bfa5", "#304ffe",
]


class LightPage(PageBase):
    title = "Işık ve LED"
    subtitle = "Işık çubuğu rengi, parlaklık, oyuncu LED'leri ve mikrofon LED'i."

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        lb = Card("Işık çubuğu")
        self.mode_group = QButtonGroup(self)
        modes = [("static", "Sabit renk"), ("battery", "Pil seviyesi (yeşil → kırmızı)"),
                 ("rainbow", "Gökkuşağı"), ("game", "Oyundan gelen renk (DS4 emülasyonu)"), ("off", "Kapalı")]
        self.mode_radios = {}
        for key, label in modes:
            r = QRadioButton(label)
            self.mode_group.addButton(r)
            self.mode_radios[key] = r
            lb.add(r)
            r.toggled.connect(lambda on, k=key: on and self._set_mode(k))

        crow = QHBoxLayout()
        self.color_btn = ColorButton()
        self.color_btn.colorChanged.connect(self._color_picked)
        crow.addWidget(QLabel("Renk"))
        crow.addWidget(self.color_btn)
        sw = QHBoxLayout()
        sw.setSpacing(6)
        for c in PRESET_COLORS:
            s = Swatch(QColor(c))
            s.clicked.connect(lambda _=False, col=QColor(c): self._color_picked(col))
            sw.addWidget(s)
        sw.addStretch(1)
        crow.addLayout(sw, 1)
        lb.add_layout(crow)

        self.sl_r = LabeledSlider("Kırmızı", 0, 255, 0)
        self.sl_g = LabeledSlider("Yeşil", 0, 255, 110)
        self.sl_b = LabeledSlider("Mavi", 0, 255, 255)
        for s in (self.sl_r, self.sl_g, self.sl_b):
            s.valueChanged.connect(self._rgb_changed)
            lb.add(s)
        self.sl_speed = LabeledSlider("Gökkuşağı hızı", 1, 100, 50)
        self.sl_speed.valueChanged.connect(self._speed_changed)
        lb.add(self.sl_speed)
        brow = QHBoxLayout()
        brow.addWidget(QLabel("Parlaklık"))
        self.cb_bright = QComboBox()
        self.cb_bright.addItems(["Yüksek", "Orta", "Düşük"])
        self.cb_bright.currentIndexChanged.connect(self._bright_changed)
        brow.addWidget(self.cb_bright)
        brow.addStretch(1)
        lb.add_layout(brow)
        row.addWidget(lb, 3)

        right = QWidget()
        from PySide6.QtWidgets import QVBoxLayout
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(14)

        pl = Card("Oyuncu LED'leri")
        g = QGridLayout()
        self.led_checks = []
        for i in range(5):
            c = QCheckBox()
            c.setToolTip(f"LED {i + 1}")
            c.toggled.connect(self._leds_changed)
            self.led_checks.append(c)
            g.addWidget(c, 0, i)
        pl.add_layout(g)
        prow = QHBoxLayout()
        for n, label in [(0, "Kapalı"), (1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "Hepsi")]:
            b = QPushButton(label)
            b.setObjectName("preset")
            b.clicked.connect(lambda _=False, k=n: self._set_leds(P.PLAYER_LED_PATTERNS[k]))
            prow.addWidget(b)
        prow.addStretch(1)
        pl.add_layout(prow)
        self.cb_fade = QCheckBox("Yumuşak geçiş (fade)")
        self.cb_fade.toggled.connect(self._fade_changed)
        pl.add(self.cb_fade)
        rl.addWidget(pl)

        mic = Card("Mikrofon")
        mrow = QHBoxLayout()
        mrow.addWidget(QLabel("Mikrofon LED'i"))
        self.cb_mic_led = QComboBox()
        self.cb_mic_led.addItems(["Kapalı", "Açık", "Yanıp sönen"])
        self.cb_mic_led.currentIndexChanged.connect(self._mic_led_changed)
        mrow.addWidget(self.cb_mic_led)
        mrow.addStretch(1)
        mic.add_layout(mrow)
        self.cb_mic_mute = QCheckBox("Mikrofonu sustur")
        self.cb_mic_mute.toggled.connect(self._mic_mute_changed)
        mic.add(self.cb_mic_mute)
        rl.addWidget(mic)
        rl.addStretch(1)
        row.addWidget(right, 2)
        self.content.addLayout(row)

    # -- yükleme ---------------------------------------------------------
    def refresh(self):
        self._loading = True
        p = self.profile
        r = self.mode_radios.get(p.lightbar_mode) or self.mode_radios["static"]
        r.setChecked(True)
        c = p.lightbar_color
        self.color_btn.setColor(QColor(int(c[0]), int(c[1]), int(c[2])))
        self.sl_r.setValue(c[0]); self.sl_g.setValue(c[1]); self.sl_b.setValue(c[2])
        self.sl_speed.setValue(p.rainbow_speed)
        self.cb_bright.setCurrentIndex(max(0, min(2, p.lightbar_brightness)))
        for i, cb in enumerate(self.led_checks):
            cb.setChecked(bool(p.player_leds & (1 << i)))
        self.cb_fade.setChecked(p.player_led_fade)
        self.cb_mic_led.setCurrentIndex(max(0, min(2, p.mic_led)))
        self.cb_mic_mute.setChecked(p.mic_mute)
        self._loading = False

    # -- değişiklikler ---------------------------------------------------
    def _commit(self):
        if not self._loading:
            self.service.update_outputs()

    def _set_mode(self, key):
        if self._loading:
            return
        self.profile.lightbar_mode = key
        self._commit()

    def _color_picked(self, c: QColor):
        self._loading = True
        self.sl_r.setValue(c.red()); self.sl_g.setValue(c.green()); self.sl_b.setValue(c.blue())
        self.color_btn.setColor(c)
        self._loading = False
        self._rgb_changed()

    def _rgb_changed(self, *_):
        if self._loading:
            return
        rgb = [self.sl_r.value(), self.sl_g.value(), self.sl_b.value()]
        self.profile.lightbar_color = rgb
        self.color_btn.setColor(QColor(*rgb))
        if self.profile.lightbar_mode not in ("static",):
            self.mode_radios["static"].setChecked(True)
        self._commit()

    def _speed_changed(self, v):
        if self._loading:
            return
        self.profile.rainbow_speed = v
        self._commit()

    def _bright_changed(self, i):
        if self._loading:
            return
        self.profile.lightbar_brightness = i
        self._commit()

    def _leds_changed(self, *_):
        if self._loading:
            return
        mask = 0
        for i, cb in enumerate(self.led_checks):
            if cb.isChecked():
                mask |= 1 << i
        self.profile.player_leds = mask
        self._commit()

    def _set_leds(self, mask):
        self._loading = True
        for i, cb in enumerate(self.led_checks):
            cb.setChecked(bool(mask & (1 << i)))
        self._loading = False
        self._leds_changed()

    def _fade_changed(self, on):
        if self._loading:
            return
        self.profile.player_led_fade = on
        self._commit()

    def _mic_led_changed(self, i):
        if self._loading:
            return
        self.profile.mic_led = i
        self._commit()

    def _mic_mute_changed(self, on):
        if self._loading:
            return
        self.profile.mic_mute = on
        self._commit()
