"""Offline HTML preview widget with a Qt WebEngine preference."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser, QWidget

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - depends on the selected PySide6 wheel
    QWebEngineView = None  # type: ignore[assignment,misc]


class PlotView:
    """Small adapter over WebEngine with a text-browser fallback."""

    def __init__(self) -> None:
        if QWebEngineView is None:
            self.widget: QWidget = QTextBrowser()
        else:
            self.widget = QWebEngineView()

    def set_html(self, content: str) -> None:
        """Display self-contained HTML without requiring network access."""
        if isinstance(self.widget, QTextBrowser):
            self.widget.setHtml(content)
        else:
            cast(Any, self.widget).setHtml(content, QUrl("about:blank"))
