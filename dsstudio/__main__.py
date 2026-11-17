"""Giriş noktası: python -m dsstudio  (ya da run.py)."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    log_dir = Path(os.environ.get("APPDATA", str(Path.home()))) / "DualSensePilot"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.handlers.RotatingFileHandler(
                      log_dir / "dsstudio.log", encoding="utf-8", maxBytes=2_000_000, backupCount=3),
                  logging.StreamHandler(sys.stderr)],
    )
    log = logging.getLogger("dsstudio")

    from PySide6.QtCore import Qt, QSharedMemory
    from PySide6.QtGui import QPalette, QColor
    from PySide6.QtWidgets import QApplication, QMessageBox

    app = QApplication(argv)
    app.setApplicationName("DualSensePilot")
    app.setOrganizationName("DualSensePilot")
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")

    # tek örnek koruması
    shm = QSharedMemory("DualSensePilot-single-instance")
    if not shm.create(1):
        QMessageBox.information(None, "DualSensePilot", "Uygulama zaten çalışıyor (sistem tepsisine bak).")
        return 0

    from .ui import theme
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor(theme.BG))
    pal.setColor(QPalette.WindowText, QColor(theme.TEXT))
    pal.setColor(QPalette.Base, QColor(theme.BG3))
    pal.setColor(QPalette.Text, QColor(theme.TEXT))
    pal.setColor(QPalette.Button, QColor(theme.BG3))
    pal.setColor(QPalette.ButtonText, QColor(theme.TEXT))
    pal.setColor(QPalette.Highlight, QColor(theme.ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("white"))
    app.setPalette(pal)
    app.setStyleSheet(theme.QSS)

    from .core.service import ControllerService
    from .ui.main_window import MainWindow

    service = ControllerService()
    win = MainWindow(service)
    minimized = "--minimized" in argv or service.store.settings.start_minimized
    if minimized and win.tray.isVisible():
        win.hide()
    else:
        win.show()
    log.info("uygulama başladı")
    rc = app.exec()
    try:
        service.shutdown()
    except Exception:  # noqa: BLE001
        log.exception("kapanış hatası")
    return rc


if __name__ == "__main__":
    sys.exit(main())
