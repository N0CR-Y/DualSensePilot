"""Uygulama simgesini assets\\app.ico olarak üretir (build için)."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
root = Path(__file__).resolve().parent
sys.path.insert(0, str(root))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])
from dsstudio.ui.widgets import make_app_icon  # noqa: E402

out = root / "assets"
out.mkdir(exist_ok=True)
pm = make_app_icon(size=256).pixmap(256, 256)
ok = pm.save(str(out / "app.ico"), "ICO")
print("ico", ok, out / "app.ico")
