"""Reusable Qt thread-pool worker with typed progress delivery."""

from __future__ import annotations

import traceback
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    """Signals emitted by a function worker."""

    finished = Signal(object)
    failed = Signal(str)
    progress = Signal(object)


class FunctionWorker(QRunnable):
    """Run a callable outside the GUI thread."""

    def __init__(
        self,
        function: Callable[[Callable[[object], None]], Any],
    ) -> None:
        super().__init__()
        self.function = function
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        """Execute the callable and convert uncaught failures to a safe message."""
        try:
            result = self.function(self.signals.progress.emit)
        except Exception as exc:
            detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            self.signals.failed.emit(detail)
        else:
            self.signals.finished.emit(result)
