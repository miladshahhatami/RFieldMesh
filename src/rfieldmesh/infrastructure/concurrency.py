"""Thread-safe cooperative cancellation primitives."""

from __future__ import annotations

import threading


class CancellationToken:
    """A minimal thread-safe cooperative cancellation token."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Request cancellation."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        """Return whether cancellation has been requested."""
        return self._event.is_set()

    def reset(self) -> None:
        """Clear cancellation before a new operation."""
        self._event.clear()
