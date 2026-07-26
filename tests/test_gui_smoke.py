"""Headless desktop construction smoke test."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

import pytest

try:
    from PySide6.QtWidgets import QApplication

    from rfieldmesh.gui.main_window import MainWindow
except ImportError as exc:
    pytest.skip(
        f"Qt runtime libraries are unavailable in this environment: {exc}",
        allow_module_level=True,
    )


@pytest.mark.gui
def test_main_window_constructs_five_tab_workflow() -> None:
    application = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert application.applicationName() is not None
    assert window.tabs.count() == 5
    assert window.tabs.tabText(0) == "1. Model"
    assert window.tabs.tabText(4) == "5. Output and batch generation"
    assert window.youngs.isChecked()
    assert not window.density.isChecked()
    window.close()
