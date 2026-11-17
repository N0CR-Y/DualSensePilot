"""Koyu gradyan tema (cam kartlar) — QSS."""

ACCENT = "#27d3b4"        # nane/turkuaz
ACCENT_HI = "#52ecd0"
ACCENT_TEXT = "#04211b"   # vurgu rengi üstündeki yazı
BG = "#0b1330"
BG2 = "#141b3d"
BG3 = "#222a57"
BORDER = "#3a4580"
TEXT = "#eef1ff"
MUTED = "#a3acd6"
POPUP = "#182049"

GRADIENT = ("qlineargradient(x1:0, y1:0, x2:1, y2:1, "
            "stop:0 #081229, stop:0.5 #162c63, stop:1 #3a1c6b)")

QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog {{
    background: {GRADIENT};
}}
QWidget#root {{
    background: {GRADIENT};
}}
QWidget#topbar {{
    background: rgba(0, 0, 0, 30%);
    border-bottom: 1px solid rgba(255, 255, 255, 12%);
}}
QToolButton#nav {{
    padding: 8px 12px;
    border: 1px solid transparent;
    border-radius: 18px;
    margin: 0 1px;
    color: {MUTED};
    font-size: 13px;
    font-weight: 500;
}}
QToolButton#nav:hover {{
    background: rgba(255, 255, 255, 10%);
    color: {TEXT};
}}
QToolButton#nav:checked {{
    background: {ACCENT};
    color: {ACCENT_TEXT};
    font-weight: 700;
}}
QLabel#topProfile {{
    font-size: 13px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#topEmu {{
    font-size: 12px;
    color: {MUTED};
}}
QFrame#card {{
    background: rgba(255, 255, 255, 8%);
    border: 1px solid rgba(255, 255, 255, 16%);
    border-radius: 16px;
}}
QLabel#cardTitle {{
    font-size: 14px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageTitle {{
    font-size: 22px;
    font-weight: 700;
}}
QLabel#muted {{
    color: {MUTED};
}}
QLabel#badgeOk {{
    background: rgba(62, 224, 143, 20%); color: #5cf0a8; border-radius: 10px; padding: 3px 10px; font-weight: 600;
}}
QLabel#badgeOff {{
    background: rgba(255, 92, 92, 20%); color: #ff8f8f; border-radius: 10px; padding: 3px 10px; font-weight: 600;
}}
QLabel#badgeInfo {{
    background: rgba(100, 170, 255, 22%); color: #9ccaff; border-radius: 10px; padding: 3px 10px; font-weight: 600;
}}
QPushButton {{
    background: rgba(255, 255, 255, 10%);
    border: 1px solid rgba(255, 255, 255, 18%);
    border-radius: 10px;
    padding: 7px 14px;
}}
QPushButton:hover {{ background: rgba(255, 255, 255, 18%); }}
QPushButton:pressed {{ background: rgba(255, 255, 255, 6%); }}
QPushButton:disabled {{ color: #6a74a3; background: rgba(255, 255, 255, 4%); }}
QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {ACCENT_TEXT};
    font-weight: 700;
}}
QPushButton#primary:hover {{ background: {ACCENT_HI}; }}
QPushButton#danger {{
    background: rgba(255, 92, 92, 18%); border: 1px solid rgba(255, 92, 92, 40%); color: #ff9a9a;
}}
QPushButton#danger:hover {{ background: rgba(255, 92, 92, 30%); }}
QPushButton#preset {{
    padding: 5px 12px; border-radius: 14px;
}}
QPushButton#preset:hover {{ background: {ACCENT}; color: {ACCENT_TEXT}; }}
QComboBox, QLineEdit, QSpinBox, QListWidget, QPlainTextEdit, QTextEdit {{
    background: rgba(0, 0, 0, 28%);
    border: 1px solid rgba(255, 255, 255, 18%);
    border-radius: 10px;
    padding: 5px 8px;
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {POPUP};
    border: 1px solid {BORDER};
    selection-background-color: {ACCENT};
    selection-color: {ACCENT_TEXT};
}}
QListWidget::item {{ padding: 6px 8px; border-radius: 8px; }}
QListWidget::item:selected {{ background: {ACCENT}; color: {ACCENT_TEXT}; }}
QCheckBox, QRadioButton {{ spacing: 8px; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 16px; height: 16px;
}}
QCheckBox::indicator {{
    border: 1px solid rgba(255, 255, 255, 35%); border-radius: 5px; background: rgba(0, 0, 0, 25%);
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QRadioButton::indicator {{
    border: 1px solid rgba(255, 255, 255, 35%); border-radius: 8px; background: rgba(0, 0, 0, 25%);
}}
QRadioButton::indicator:checked {{ border: 1px solid {ACCENT}; background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5, stop:0 {ACCENT}, stop:0.5 {ACCENT}, stop:0.62 rgba(0,0,0,25%), stop:1 rgba(0,0,0,25%)); }}
QSlider::groove:horizontal {{
    height: 6px; background: rgba(255, 255, 255, 14%); border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {ACCENT}; border-radius: 3px;
}}
QSlider::handle:horizontal {{
    width: 16px; height: 16px; margin: -5px 0; border-radius: 8px;
    background: white; border: 2px solid {ACCENT};
}}
QSlider::groove:vertical {{
    width: 6px; background: rgba(255, 255, 255, 14%); border-radius: 3px;
}}
QSlider::add-page:vertical {{
    background: {ACCENT}; border-radius: 3px;
}}
QSlider::handle:vertical {{
    height: 16px; width: 16px; margin: 0 -5px; border-radius: 8px;
    background: white; border: 2px solid {ACCENT};
}}
QProgressBar {{
    background: rgba(255, 255, 255, 12%); border: none; border-radius: 6px; height: 12px; text-align: center;
    color: {TEXT}; font-size: 10px;
}}
QProgressBar::chunk {{ background: #3ee08f; border-radius: 6px; }}
QProgressBar#rumble::chunk {{ background: {ACCENT}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{
    background: rgba(255, 255, 255, 22%); border-radius: 5px; min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: rgba(255, 255, 255, 22%); border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QStatusBar {{ background: rgba(0, 0, 0, 25%); border-top: 1px solid rgba(255, 255, 255, 10%); color: {MUTED}; }}
QGroupBox {{
    border: 1px solid rgba(255, 255, 255, 16%); border-radius: 10px; margin-top: 12px; padding: 10px 8px 8px 8px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 12px; padding: 0 4px; color: {MUTED};
}}
QToolTip {{ background: {POPUP}; color: {TEXT}; border: 1px solid {BORDER}; }}
QMenu {{ background: {POPUP}; border: 1px solid {BORDER}; }}
QMenu::item {{ padding: 6px 20px; }}
QMenu::item:selected {{ background: {ACCENT}; color: {ACCENT_TEXT}; }}
QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 8px; }}
QTabBar::tab {{ background: {BG2}; padding: 7px 14px; border: 1px solid {BORDER}; border-bottom: none;
    border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; color: {MUTED}; }}
QTabBar::tab:selected {{ background: {BG3}; color: {TEXT}; }}
QMessageBox, QInputDialog {{ background: {BG2}; }}
"""


