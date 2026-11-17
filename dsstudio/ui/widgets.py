"""Ortak arayüz bileşenleri."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import (QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QIcon, QPixmap, QLinearGradient,
                           QRadialGradient, QPainterPath, QPolygonF)
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget,
                               QPushButton, QColorDialog, QSizePolicy, QGridLayout)

from ..core import protocol as P
from . import theme


class Card(QFrame):
    """Başlıklı kart."""

    def __init__(self, title: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(10)
        if title:
            t = QLabel(title)
            t.setObjectName("cardTitle")
            self._layout.addWidget(t)
        self.body = QVBoxLayout()
        self.body.setSpacing(8)
        self._layout.addLayout(self.body)

    def add(self, w: QWidget):
        self.body.addWidget(w)
        return w

    def add_layout(self, l):
        self.body.addLayout(l)
        return l


class LabeledSlider(QWidget):
    valueChanged = Signal(int)

    def __init__(self, label: str, lo: int, hi: int, value: int = 0, unit: str = "", parent=None):
        super().__init__(parent)
        self.unit = unit
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)
        self.label = QLabel(label)
        self.label.setMinimumWidth(130)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setValue(value)
        self.value_label = QLabel()
        self.value_label.setMinimumWidth(52)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setObjectName("muted")
        lay.addWidget(self.label)
        lay.addWidget(self.slider, 1)
        lay.addWidget(self.value_label)
        self.slider.valueChanged.connect(self._on_change)
        self._on_change(value)

    def _on_change(self, v):
        self.value_label.setText(f"{v}{(' ' + self.unit) if self.unit else ''}")
        self.valueChanged.emit(v)

    def value(self) -> int:
        return self.slider.value()

    def setValue(self, v: int):
        self.slider.setValue(int(v))

    def setRange(self, lo: int, hi: int):
        self.slider.setRange(lo, hi)


class ColorButton(QPushButton):
    colorChanged = Signal(QColor)

    def __init__(self, color=QColor(0, 110, 255), parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self.setFixedSize(64, 32)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self):
        self.setStyleSheet(f"QPushButton {{ background: {self._color.name()}; border: 2px solid rgba(255,255,255,60%); border-radius: 10px; }}")

    def _pick(self):
        c = QColorDialog.getColor(self._color, self, "Işık çubuğu rengi")
        if c.isValid():
            self.setColor(c)
            self.colorChanged.emit(c)

    def color(self) -> QColor:
        return QColor(self._color)

    def setColor(self, c: QColor):
        self._color = QColor(c)
        self._refresh()


class Swatch(QPushButton):
    def __init__(self, color: QColor, parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.setFixedSize(26, 26)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(f"QPushButton {{ background: {self.color.name()}; border: 1px solid #00000066; border-radius: 13px; }}"
                           f"QPushButton:hover {{ border: 2px solid white; }}")


class Badge(QLabel):
    def __init__(self, text="", kind="info", parent=None):
        super().__init__(text, parent)
        self.setKind(kind)

    def setKind(self, kind: str):
        self.setObjectName({"ok": "badgeOk", "off": "badgeOff"}.get(kind, "badgeInfo"))
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
#  Gerçekçi DualSense çizimi
# ---------------------------------------------------------------------------
CW, CH = 620.0, 400.0
_MIRROR_AXIS = 620.0


def _mx(pt):
    return (_MIRROR_AXIS - pt[0], pt[1])


def _build_body() -> QPainterPath:
    """Sağ yarıyı bezier ile tanımlayıp aynalayarak simetrik gövde üretir."""
    start = (310.0, 98.0)
    segs = [
        ((380, 98), (470, 100), (512, 112)),     # üst kenar → omuz
        ((562, 128), (596, 200), (592, 272)),    # dış kenar
        ((588, 338), (556, 376), (522, 372)),    # sap altı
        ((494, 368), (474, 322), (450, 292)),    # iç kenar
        ((420, 258), (380, 262), (310, 262)),    # alt orta
    ]
    path = QPainterPath(QPointF(*start))
    starts = [start] + [s[2] for s in segs]
    for c1, c2, e in segs:
        path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*e))
    for i in range(len(segs) - 1, -1, -1):
        c1, c2, _e = segs[i]
        path.cubicTo(QPointF(*_mx(c2)), QPointF(*_mx(c1)), QPointF(*_mx(starts[i])))
    path.closeSubpath()
    return path


def _font(px: int, bold: bool = False) -> QFont:
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


class ControllerView(QWidget):
    """Kolun canlı durumunu gerçekçi biçimde çizer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state: P.InputState | None = None
        self.lightbar = QColor(0, 110, 255)
        self._body = _build_body()
        self.setMinimumSize(520, 336)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_state(self, s: P.InputState | None, lightbar=None):
        self.state = s
        if lightbar is not None:
            self.lightbar = QColor(*lightbar)
        self.update()

    # -- yardımcılar -------------------------------------------------------
    @staticmethod
    def _accent() -> QColor:
        return QColor(theme.ACCENT)

    @staticmethod
    def _text(p: QPainter, rect: QRectF, text: str, px=12, bold=False, color=None, align=Qt.AlignCenter):
        p.setFont(_font(px, bold))
        p.setPen(color or QColor(theme.TEXT))
        p.drawText(rect, align, text)

    # -- ana çizim ----------------------------------------------------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing | QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        k = min(w / CW, h / CH)
        p.translate((w - CW * k) / 2, (h - CH * k) / 2)
        p.scale(k, k)
        connected = self.state is not None
        s = self.state or P.InputState()
        p.setOpacity(1.0 if connected else 0.5)

        self._draw_shadow(p)
        self._draw_triggers(p, s)
        self._draw_shoulders(p, s)
        self._draw_body(p)
        self._draw_touchpad(p, s)
        self._draw_lightbar(p)
        self._draw_dpad(p, s)
        self._draw_face(p, s)
        self._draw_sticks(p, s)
        self._draw_center(p, s)

        p.setOpacity(1.0)
        muted = QColor(theme.MUTED)
        if connected:
            self._text(p, QRectF(0, 380, CW, 18),
                       f"Sol çubuk {s.lx}, {s.ly}      Sağ çubuk {s.rx}, {s.ry}", 12, False, muted)
        else:
            self._text(p, QRectF(0, 380, CW, 18),
                       "Kol bağlı değil. PS tuşuna bas ya da USB ile tak.", 12, False, muted)
        p.end()

    # -- parçalar ---------------------------------------------------------
    def _draw_shadow(self, p: QPainter):
        p.save()
        p.translate(310, 376)
        p.scale(1.0, 0.09)
        g = QRadialGradient(QPointF(0, 0), 270)
        g.setColorAt(0.0, QColor(0, 0, 0, 150))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 0), 270, 270)
        p.restore()

    def _draw_triggers(self, p: QPainter, s: P.InputState):
        acc = self._accent()
        for x, val, label in ((136.0, s.l2, "L2"), (416.0, s.r2, "R2")):
            rect = QRectF(x, 46, 68, 62)
            path = QPainterPath()
            path.addRoundedRect(rect, 18, 18)
            g = QLinearGradient(0, 46, 0, 108)
            g.setColorAt(0, QColor("#505670"))
            g.setColorAt(1, QColor("#1d2030"))
            p.setPen(QPen(QColor(0, 0, 0, 140), 1.3))
            p.setBrush(g)
            p.drawPath(path)
            frac = max(0.0, min(1.0, val / 255.0))
            if frac > 0:
                p.save()
                p.setClipPath(path)
                gg = QLinearGradient(0, 46, 0, 108)
                gg.setColorAt(0, acc.lighter(130))
                gg.setColorAt(1, acc)
                p.setPen(Qt.NoPen)
                p.setBrush(gg)
                p.drawRect(QRectF(x, 46, 68, 62 * frac))
                p.restore()
            self._text(p, QRectF(x - 14, 24, 96, 18), f"{label}  {int(round(frac * 100))}%", 12, True)

    def _draw_shoulders(self, p: QPainter, s: P.InputState):
        acc = self._accent()
        for x, pressed in ((124.0, s.l1), (404.0, s.r1)):
            rect = QRectF(x, 82, 92, 32)
            g = QLinearGradient(0, 82, 0, 114)
            if pressed:
                g.setColorAt(0, acc.lighter(125))
                g.setColorAt(1, acc)
            else:
                g.setColorAt(0, QColor("#fdfdff"))
                g.setColorAt(1, QColor("#c3c9d6"))
            p.setPen(QPen(QColor(30, 35, 60, 120), 1.4))
            p.setBrush(g)
            p.drawRoundedRect(rect, 14, 14)

    def _draw_body(self, p: QPainter):
        body = self._body
        # kabuk
        g = QLinearGradient(0, 96, 0, 376)
        g.setColorAt(0.0, QColor("#ffffff"))
        g.setColorAt(0.35, QColor("#eceff6"))
        g.setColorAt(0.75, QColor("#cdd3e0"))
        g.setColorAt(1.0, QColor("#a6aec2"))
        p.setPen(QPen(QColor(30, 35, 70, 130), 1.6))
        p.setBrush(g)
        p.drawPath(body)

        p.save()
        p.setClipPath(body)
        gl = QLinearGradient(0, 96, 0, 210)
        gl.setColorAt(0, QColor(255, 255, 255, 170))
        gl.setColorAt(1, QColor(255, 255, 255, 0))
        p.fillRect(QRectF(0, 96, CW, 114), gl)
        # sap gölgeleri
        for cx, x0 in ((535.0, 310.0), (85.0, 0.0)):
            rg = QRadialGradient(QPointF(cx, 270), 150)
            rg.setColorAt(0.55, QColor(20, 25, 60, 0))
            rg.setColorAt(1.0, QColor(20, 25, 60, 75))
            p.save()
            p.setClipRect(QRectF(x0, 0, 310, CH), Qt.IntersectClip)
            p.fillRect(QRectF(0, 90, CW, 300), rg)
            p.restore()
        p.restore()

        # siyah orta panel
        rr = QPainterPath()
        rr.addRoundedRect(QRectF(188, 60, 244, 250), 40, 40)
        panel = body.intersected(rr)
        pg = QLinearGradient(0, 96, 0, 270)
        pg.setColorAt(0, QColor("#2b3040"))
        pg.setColorAt(1, QColor("#0a0c11"))
        p.setPen(QPen(QColor(255, 255, 255, 45), 1.2))
        p.setBrush(pg)
        p.drawPath(panel)

    def _draw_touchpad(self, p: QPainter, s: P.InputState):
        rect = QRectF(238, 108, 144, 76)
        g = QLinearGradient(0, 108, 0, 184)
        g.setColorAt(0, QColor("#3a4051"))
        g.setColorAt(1, QColor("#1b1e29"))
        p.setPen(QPen(QColor(255, 255, 255, 55), 1.3))
        p.setBrush(g)
        p.drawRoundedRect(rect, 16, 16)
        if s.touch_btn:
            c = self._accent()
            c.setAlpha(95)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRoundedRect(rect, 16, 16)
        for tp in s.touch:
            if not tp.active:
                continue
            tx = rect.left() + tp.x / P.TOUCHPAD_W * rect.width()
            ty = rect.top() + tp.y / P.TOUCHPAD_H * rect.height()
            rg = QRadialGradient(QPointF(tx, ty), 22)
            rg.setColorAt(0, QColor(255, 255, 255, 220))
            rg.setColorAt(0.35, QColor(255, 214, 90, 200))
            rg.setColorAt(1, QColor(255, 214, 90, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(QPointF(tx, ty), 22, 22)

    def _draw_lightbar(self, p: QPainter):
        lb = QColor(self.lightbar)
        dark = lb.red() + lb.green() + lb.blue() < 12
        if dark:
            lb = QColor(255, 255, 255, 30)
        else:
            amb = QRadialGradient(QPointF(310, 146), 150)
            c0 = QColor(lb)
            c0.setAlpha(60)
            c1 = QColor(lb)
            c1.setAlpha(0)
            amb.setColorAt(0, c0)
            amb.setColorAt(1, c1)
            p.save()
            p.setClipPath(self._body)
            p.setPen(Qt.NoPen)
            p.setBrush(amb)
            p.drawRect(QRectF(150, 60, 320, 240))
            p.restore()
        for sign in (0, 1):
            path = QPainterPath()
            if sign == 0:
                path.moveTo(230, 112)
                path.quadTo(220, 147, 230, 182)
            else:
                path.moveTo(390, 112)
                path.quadTo(400, 147, 390, 182)
            if not dark:
                for width, alpha in ((18, 28), (11, 60)):
                    c = QColor(lb)
                    c.setAlpha(alpha)
                    p.setPen(QPen(c, width, Qt.SolidLine, Qt.RoundCap))
                    p.setBrush(Qt.NoBrush)
                    p.drawPath(path)
            p.setPen(QPen(lb, 4.5, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

    def _draw_dpad(self, p: QPainter, s: P.InputState):
        acc = self._accent()
        cx, cy = 150.0, 168.0
        arms = [
            (QRectF(cx - 11, cy - 34, 22, 36), s.dpad_up, [(cx, cy - 26), (cx - 5, cy - 19), (cx + 5, cy - 19)]),
            (QRectF(cx - 11, cy - 2, 22, 36), s.dpad_down, [(cx, cy + 26), (cx - 5, cy + 19), (cx + 5, cy + 19)]),
            (QRectF(cx - 34, cy - 11, 36, 22), s.dpad_left, [(cx - 26, cy), (cx - 19, cy - 5), (cx - 19, cy + 5)]),
            (QRectF(cx - 2, cy - 11, 36, 22), s.dpad_right, [(cx + 26, cy), (cx + 19, cy - 5), (cx + 19, cy + 5)]),
        ]
        # temel gölge
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        for r, _pr, _t in arms:
            p.drawRoundedRect(r.translated(1.5, 2.5), 8, 8)
        for r, pressed, tri in arms:
            g = QLinearGradient(r.topLeft(), r.bottomRight())
            if pressed:
                g.setColorAt(0, acc.lighter(130))
                g.setColorAt(1, acc)
            else:
                g.setColorAt(0, QColor("#f7f8fc"))
                g.setColorAt(1, QColor("#b9c0cf"))
            p.setPen(QPen(QColor(30, 35, 70, 120), 1.2))
            p.setBrush(g)
            p.drawRoundedRect(r, 8, 8)
        for r, pressed, tri in arms:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(4, 33, 27) if pressed else QColor(70, 78, 105, 190))
            p.drawPolygon(QPolygonF([QPointF(*pt) for pt in tri]))

    def _glass_circle(self, p: QPainter, c: QPointF, r: float, pressed: bool, glow: QColor):
        if pressed:
            gc = QColor(glow)
            gc.setAlpha(90)
            rg = QRadialGradient(c, r + 12)
            rg.setColorAt(0.6, gc)
            gc2 = QColor(glow)
            gc2.setAlpha(0)
            rg.setColorAt(1.0, gc2)
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(c, r + 12, r + 12)
        g = QRadialGradient(QPointF(c.x() - r * 0.35, c.y() - r * 0.45), r * 1.6)
        if pressed:
            g.setColorAt(0, glow.lighter(140))
            g.setColorAt(1, glow)
        else:
            g.setColorAt(0, QColor("#ffffff"))
            g.setColorAt(1, QColor("#b4bccd"))
        p.setPen(QPen(QColor(30, 35, 70, 140), 1.3))
        p.setBrush(g)
        p.drawEllipse(c, r, r)

    def _draw_face(self, p: QPainter, s: P.InputState):
        cx, cy, d, r = 470.0, 168.0, 31.0, 16.0
        items = [
            ("tri", QPointF(cx, cy - d), s.triangle, QColor("#17b88c")),
            ("cir", QPointF(cx + d, cy), s.circle, QColor("#ec4a60")),
            ("cro", QPointF(cx, cy + d), s.cross, QColor("#3f86f7")),
            ("squ", QPointF(cx - d, cy), s.square, QColor("#d95fc8")),
        ]
        for kind, c, pressed, col in items:
            self._glass_circle(p, c, r, pressed, col)
            sym = QColor("white") if pressed else col.darker(105)
            p.setPen(QPen(sym, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            x, y = c.x(), c.y()
            if kind == "tri":
                p.drawPolygon(QPolygonF([QPointF(x, y - 7.5), QPointF(x + 7.5, y + 5.5), QPointF(x - 7.5, y + 5.5)]))
            elif kind == "cir":
                p.drawEllipse(c, 7, 7)
            elif kind == "cro":
                p.drawLine(QPointF(x - 6.5, y - 6.5), QPointF(x + 6.5, y + 6.5))
                p.drawLine(QPointF(x + 6.5, y - 6.5), QPointF(x - 6.5, y + 6.5))
            else:
                p.drawRect(QRectF(x - 6.5, y - 6.5, 13, 13))

    def _draw_sticks(self, p: QPainter, s: P.InputState):
        acc = self._accent()
        for cx, cy, ax, ay, pressed in ((232.0, 224.0, s.lx, s.ly, s.l3), (388.0, 224.0, s.rx, s.ry, s.r3)):
            c = QPointF(cx, cy)
            well = QRadialGradient(c, 42)
            well.setColorAt(0, QColor("#05060a"))
            well.setColorAt(0.8, QColor("#14161e"))
            well.setColorAt(1, QColor("#2a2e3b"))
            p.setPen(QPen(QColor(255, 255, 255, 40), 1.2))
            p.setBrush(well)
            p.drawEllipse(c, 41, 41)
            dx = (ax - 128) / 128.0 * 12
            dy = (ay - 128) / 128.0 * 12
            cap = QPointF(cx + dx, cy + dy)
            # gölge
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 110))
            p.drawEllipse(QPointF(cap.x() + 1.5, cap.y() + 3), 28, 28)
            g = QRadialGradient(QPointF(cap.x() - 8, cap.y() - 10), 40)
            g.setColorAt(0, QColor("#6c7288"))
            g.setColorAt(1, QColor("#242733"))
            p.setPen(QPen(acc if pressed else QColor(0, 0, 0, 160), 3.0 if pressed else 1.4))
            p.setBrush(g)
            p.drawEllipse(cap, 28, 28)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 38), 1.0))
            p.drawEllipse(cap, 20, 20)
            p.setPen(QPen(QColor(255, 255, 255, 26), 1.0))
            p.drawEllipse(cap, 12, 12)

    def _draw_center(self, p: QPainter, s: P.InputState):
        acc = self._accent()
        # create / options
        for x, pressed in ((202.0, s.create), (409.0, s.options)):
            r = QRectF(x, 114, 9, 24)
            p.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
            p.setBrush(acc if pressed else QColor("#3b4153"))
            p.drawRoundedRect(r, 4.5, 4.5)
        # PS
        c = QPointF(310, 226)
        g = QRadialGradient(QPointF(c.x() - 4, c.y() - 5), 18)
        if s.ps:
            g.setColorAt(0, acc.lighter(140))
            g.setColorAt(1, acc)
        else:
            g.setColorAt(0, QColor("#4a5066"))
            g.setColorAt(1, QColor("#161922"))
        p.setPen(QPen(QColor(255, 255, 255, 70), 1.2))
        p.setBrush(g)
        p.drawEllipse(c, 13, 13)
        self._text(p, QRectF(c.x() - 13, c.y() - 13, 26, 26), "PS", 10, True,
                   QColor(theme.ACCENT_TEXT) if s.ps else QColor(255, 255, 255, 220))
        # mikrofon tuşu + LED
        muted = s.mic_muted
        r = QRectF(297, 251, 26, 10)
        p.setPen(QPen(QColor(255, 255, 255, 50), 1.0))
        p.setBrush(QColor("#ff9d3d") if (muted or s.mic_btn) else QColor("#2e3342"))
        p.drawRoundedRect(r, 5, 5)
        if muted:
            rg = QRadialGradient(r.center(), 20)
            rg.setColorAt(0, QColor(255, 157, 61, 120))
            rg.setColorAt(1, QColor(255, 157, 61, 0))
            p.setPen(Qt.NoPen)
            p.setBrush(rg)
            p.drawEllipse(r.center(), 20, 20)


# ---------------------------------------------------------------------------
class StatusStrip(QWidget):
    """Üst çubuk sol: bağlantı durumu, bağlantı türü, pil ve şarj."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(232, 52)
        self._st = (False, "", 0, False, False, False)

    def set_status(self, connected: bool, kind: str, pct: int, charging: bool, full: bool, error: bool):
        st = (bool(connected), kind, int(pct), bool(charging), bool(full), bool(error))
        if st != self._st:
            self._st = st
            self.update()

    def paintEvent(self, ev):
        connected, kind, pct, charging, full, error = self._st
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.TextAntialiasing)

        # 1. satır: nokta + durum + bağlantı türü
        dot = QColor("#3ee08f") if connected else QColor("#ff6b6b")
        g = QRadialGradient(QPointF(8, 11), 9)
        g0 = QColor(dot)
        g0.setAlpha(110)
        g1 = QColor(dot)
        g1.setAlpha(0)
        g.setColorAt(0, g0)
        g.setColorAt(1, g1)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(8, 11), 9, 9)
        p.setBrush(dot)
        p.drawEllipse(QPointF(8, 11), 4.2, 4.2)
        text = "Bağlı" if connected else "Kol aranıyor…"
        f = _font(14, True)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT))
        p.drawText(QRectF(22, 0, 150, 22), Qt.AlignVCenter | Qt.AlignLeft, text)
        if connected and kind:
            tw = QFontMetrics(f).horizontalAdvance(text)
            cf = _font(11, True)
            cw = QFontMetrics(cf).horizontalAdvance(kind) + 16
            chip = QRectF(22 + tw + 10, 2, cw, 18)
            acc = QColor(theme.ACCENT)
            fill = QColor(acc)
            fill.setAlpha(40)
            p.setPen(QPen(acc, 1.0))
            p.setBrush(fill)
            p.drawRoundedRect(chip, 9, 9)
            p.setFont(cf)
            p.setPen(acc.lighter(125))
            p.drawText(chip, Qt.AlignCenter, kind)

        # 2. satır: pil
        by = 29.0
        fg = QColor(255, 255, 255, 210) if connected else QColor(255, 255, 255, 90)
        p.setPen(QPen(fg, 1.6))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, by, 34, 16), 4.5, 4.5)
        p.setPen(Qt.NoPen)
        p.setBrush(fg)
        p.drawRoundedRect(QRectF(36.5, by + 5, 3, 6), 1.2, 1.2)
        if connected:
            if charging or full:
                col = QColor(theme.ACCENT)
            elif pct > 50:
                col = QColor("#3ee08f")
            elif pct > 20:
                col = QColor("#ffc24a")
            else:
                col = QColor("#ff5c5c")
            w = max(2.0, 28.0 * max(0, min(100, pct)) / 100.0) if pct > 0 else 0
            if w:
                p.setBrush(col)
                p.drawRoundedRect(QRectF(4, by + 3, w, 10), 2.5, 2.5)
            if charging:
                bolt = QPolygonF([QPointF(20, by + 1.5), QPointF(12, by + 9.5), QPointF(17, by + 9.5),
                                  QPointF(15, by + 15), QPointF(25, by + 6.5), QPointF(19.5, by + 6.5)])
                p.setPen(QPen(QColor(0, 0, 0, 150), 0.8))
                p.setBrush(QColor("white"))
                p.drawPolygon(bolt)
            if error:
                info = "Pil hatası"
            elif full:
                info = "Şarj oldu"
            elif charging:
                info = "Şarj oluyor"
            else:
                info = "Pil ile çalışıyor"
            label = f"%{pct}  ·  {info}"
            p.setPen(QColor(theme.TEXT))
            p.setFont(_font(13, False))
            p.drawText(QRectF(48, by - 2, 200, 20), Qt.AlignVCenter | Qt.AlignLeft, label)
        else:
            p.setPen(QColor(theme.MUTED))
            p.setFont(_font(12, False))
            p.drawText(QRectF(48, by - 2, 200, 20), Qt.AlignVCenter | Qt.AlignLeft, "Pil bilgisi yok")
        p.end()


class AxisBar(QWidget):
    """-1..1 aralığında yatay gösterge (jiroskop/ivmeölçer için)."""

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.value = 0.0
        self.setFixedHeight(18)

    def set(self, v: float):
        self.value = max(-1.0, min(1.0, v))
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        p.setPen(QColor(theme.MUTED))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(0, 0, 40, h), Qt.AlignVCenter | Qt.AlignLeft, self.label)
        bar = QRectF(44, 4, w - 48, h - 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 30))
        p.drawRoundedRect(bar, 4, 4)
        mid = bar.left() + bar.width() / 2
        x = mid + self.value * bar.width() / 2
        p.setBrush(QColor(theme.ACCENT))
        if x >= mid:
            p.drawRoundedRect(QRectF(mid, bar.top(), x - mid, bar.height()), 3, 3)
        else:
            p.drawRoundedRect(QRectF(x, bar.top(), mid - x, bar.height()), 3, 3)
        p.end()


def make_app_icon(color: QColor = QColor(theme.ACCENT), size: int = 64) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    g = QLinearGradient(0, 0, size, size)
    g.setColorAt(0, color.lighter(120))
    g.setColorAt(1, color.darker(130))
    p.setBrush(QBrush(g))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(2, 2, size - 4, size - 4), size * 0.25, size * 0.25)
    p.setBrush(QColor("white"))
    s = size
    p.drawRoundedRect(QRectF(s * 0.18, s * 0.36, s * 0.64, s * 0.30), s * 0.15, s * 0.15)
    p.setBrush(color.darker(140))
    p.drawEllipse(QPointF(s * 0.34, s * 0.51), s * 0.07, s * 0.07)
    p.drawEllipse(QPointF(s * 0.66, s * 0.51), s * 0.07, s * 0.07)
    p.end()
    return QIcon(pm)


def hline():
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: rgba(255,255,255,30);")
    return f


def grid_two(pairs: list[tuple[str, QWidget]]) -> QGridLayout:
    g = QGridLayout()
    g.setHorizontalSpacing(12)
    g.setVerticalSpacing(8)
    for i, (label, w) in enumerate(pairs):
        lab = QLabel(label)
        lab.setObjectName("muted")
        g.addWidget(lab, i, 0)
        g.addWidget(w, i, 1)
    g.setColumnStretch(1, 1)
    return g

