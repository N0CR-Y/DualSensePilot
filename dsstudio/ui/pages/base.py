from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ...core.service import ControllerService


class PageBase(QWidget):
    title = ""
    subtitle = ""

    def __init__(self, service: ControllerService, parent=None):
        super().__init__(parent)
        self.service = service
        self._loading = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        inner = QWidget()
        inner.setMinimumWidth(0)
        self.content = QVBoxLayout(inner)
        self.content.setContentsMargins(24, 20, 24, 24)
        self.content.setSpacing(14)
        t = QLabel(self.title)
        t.setObjectName("pageTitle")
        self.content.addWidget(t)
        if self.subtitle:
            s = QLabel(self.subtitle)
            s.setObjectName("muted")
            s.setWordWrap(True)
            self.content.addWidget(s)
        self.build()
        self.content.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

    def build(self):
        raise NotImplementedError

    def refresh(self):
        """Profil değiştiğinde arayüzü yeniler."""

    def update_live(self):
        """Yaklaşık 30 Hz ile çağrılır (canlı veriler)."""

    @property
    def profile(self):
        return self.service.profile
