from __future__ import annotations

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from ...core import protocol as P
from ..widgets import AxisBar, Badge, Card, ControllerView
from .base import PageBase


class StatusPage(PageBase):
    title = "Durum"
    subtitle = "Kolun bağlantı durumu, pil seviyesi ve canlı giriş verileri."

    def build(self):
        row = QHBoxLayout()
        row.setSpacing(14)

        conn = Card("Bağlantı")
        self.badge = Badge("Bağlı değil", "off")
        g = QGridLayout()
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(6)
        self.lbl_transport = QLabel("-")
        self.lbl_fw = QLabel("-")
        self.lbl_mac = QLabel("-")
        self.lbl_rate = QLabel("-")
        self.lbl_audio = QLabel("-")
        self.battery = QProgressBar()
        self.battery.setRange(0, 100)
        self.battery.setFormat("%p%")
        self.lbl_charge = QLabel("")
        self.lbl_charge.setObjectName("muted")
        rows = [("Durum", self.badge), ("Bağlantı", self.lbl_transport), ("Pil", self.battery),
                ("", self.lbl_charge), ("Yazılım", self.lbl_fw), ("MAC", self.lbl_mac),
                ("Rapor hızı", self.lbl_rate), ("Ses", self.lbl_audio)]
        for i, (k, w) in enumerate(rows):
            lab = QLabel(k)
            lab.setObjectName("muted")
            g.addWidget(lab, i, 0)
            g.addWidget(w, i, 1)
        g.setColumnStretch(1, 1)
        conn.add_layout(g)
        btns = QHBoxLayout()
        self.btn_disconnect = QPushButton("Bağlantıyı kes")
        self.btn_disconnect.clicked.connect(self.service.disconnect_device)
        btns.addWidget(self.btn_disconnect)
        btns.addStretch(1)
        conn.add_layout(btns)
        hint = QLabel("Kol görünmüyorsa PS tuşuna basarak uyandır ya da USB ile bağla. "
                      "Bluetooth için Windows ayarlarından 'DualSense Wireless Controller' olarak eşleştir.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        conn.add(hint)
        conn.setMaximumWidth(380)
        row.addWidget(conn)

        view = Card("Canlı görünüm")
        self.view = ControllerView()
        view.add(self.view)
        row.addWidget(view, 1)
        self.content.addLayout(row)

        sens = Card("Sensörler ve dokunmatik yüzey")
        sg = QGridLayout()
        sg.setHorizontalSpacing(24)
        self.gyro = [AxisBar("Jir X"), AxisBar("Jir Y"), AxisBar("Jir Z")]
        self.acc = [AxisBar("İvm X"), AxisBar("İvm Y"), AxisBar("İvm Z")]
        for i, a in enumerate(self.gyro):
            sg.addWidget(a, i, 0)
        for i, a in enumerate(self.acc):
            sg.addWidget(a, i, 1)
        self.lbl_touch = QLabel("Dokunma: -")
        self.lbl_touch.setObjectName("muted")
        self.lbl_trig = QLabel("Tetik efekt durumu: -")
        self.lbl_trig.setObjectName("muted")
        sg.addWidget(self.lbl_touch, 3, 0)
        sg.addWidget(self.lbl_trig, 3, 1)
        sg.setColumnStretch(0, 1)
        sg.setColumnStretch(1, 1)
        sens.add_layout(sg)
        self.content.addWidget(sens)

        self.service.device_connected.connect(self._on_connected)
        self.service.device_disconnected.connect(self._on_disconnected)
        self._on_disconnected("")

    def _on_connected(self, label: str):
        self.badge.setText("Bağlı")
        self.badge.setKind("ok")
        self.btn_disconnect.setEnabled(True)
        dev = self.service.device
        if dev:
            self.lbl_transport.setText("Bluetooth" if dev.is_bluetooth else "USB")
            fw = dev.firmware
            if fw.get("update_version"):
                self.lbl_fw.setText(f"0x{fw['update_version']:04X}  ({fw.get('build_date', '')})")
            else:
                self.lbl_fw.setText("-")
            self.lbl_mac.setText(dev.mac or "-")

    def _on_disconnected(self, reason: str):
        self.badge.setText("Bağlı değil")
        self.badge.setKind("off")
        self.btn_disconnect.setEnabled(False)
        self.lbl_transport.setText("-")
        self.lbl_fw.setText("-")
        self.lbl_mac.setText("-")
        self.lbl_rate.setText("-")
        self.lbl_audio.setText("-")
        self.battery.setValue(0)
        self.lbl_charge.setText("")
        self.view.set_state(None, self.service.output.lightbar)

    def update_live(self):
        dev = self.service.device
        s = self.service.last_state
        self.view.set_state(s, self.service.output.lightbar)
        if dev is None or s is None:
            return
        self.lbl_transport.setText("Bluetooth" if dev.is_bluetooth else "USB")
        self.battery.setValue(s.battery_percent)
        if s.battery_error:
            self.lbl_charge.setText("Pil hatası / anormal sıcaklık")
        elif s.battery_full:
            self.lbl_charge.setText("Dolu")
        elif s.charging:
            self.lbl_charge.setText("Şarj oluyor")
        else:
            self.lbl_charge.setText("Pil ile çalışıyor")
        self.lbl_rate.setText(f"{dev.report_rate:.0f} Hz")
        audio = []
        if s.headphones:
            audio.append("Kulaklık")
        if s.mic:
            audio.append("Mikrofon")
        if s.mic_muted:
            audio.append("(sessiz)")
        self.lbl_audio.setText(" ".join(audio) if audio else "Yok")
        for i in range(3):
            self.gyro[i].set(s.gyro[i] / 32768.0 * 4)
            self.acc[i].set(s.accel[i] / P.ACC_RES_PER_G / 2)
        pts = [f"#{t.id} ({t.x},{t.y})" for t in s.touch if t.active]
        self.lbl_touch.setText("Dokunma: " + (", ".join(pts) if pts else "-"))
        self.lbl_trig.setText(f"Tetik efekt durumu: L2 0x{s.l2_feedback:02X}  R2 0x{s.r2_feedback:02X}")
