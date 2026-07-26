"""Desktop application entry point."""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import PySide6
from PySide6.QtCore import QCoreApplication, QTimer, qVersion
from PySide6.QtWidgets import QApplication

from rfieldmesh import __version__
from rfieldmesh.gui.main_window import MainWindow


def _write_smoke_report(window: MainWindow) -> None:
    """Record construction evidence when the native packaging smoke mode is enabled."""
    requested_path = os.environ.get("RFIELDMESH_SMOKE_REPORT")
    if requested_path is None:
        return
    path = Path(requested_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "schema_version": "1.0",
        "application_version": __version__,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "pyside_version": PySide6.__version__,
        "qt_version": qVersion(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "tab_count": window.tabs.count(),
        "tab_titles": [window.tabs.tabText(index) for index in range(window.tabs.count())],
        "window_visible": window.isVisible(),
    }
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    """Create the Qt application and enter its event loop."""
    existing = QCoreApplication.instance()
    owns_application = existing is None
    application = QApplication(sys.argv) if existing is None else cast(QApplication, existing)
    application.setApplicationName("RFieldMesh")
    application.setApplicationDisplayName("RFieldMesh")
    application.setApplicationVersion(__version__)
    window = MainWindow()
    window.show()
    smoke_mode = os.environ.get("RFIELDMESH_SMOKE_TEST") == "1"
    if smoke_mode:
        _write_smoke_report(window)
        QTimer.singleShot(750, application.quit)
    if not owns_application:
        return 0
    return application.exec()


if __name__ == "__main__":  # pragma: no cover - manual desktop entry point
    raise SystemExit(main())
