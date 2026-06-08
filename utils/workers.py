"""
Background worker that keeps the GUI responsive while fetching data.
"""

import threading
import tkinter as tk
from typing import Callable, Any


class AsyncWorker:
    """
    Runs a callable in a daemon thread and delivers the result (or
    exception) back to the GUI thread via a callback.

    Usage::

        def fetch():
            return client.get_latest_rates("USD")

        def on_done(result, error):
            if error:
                show_error(str(error))
            else:
                update_table(result)

        AsyncWorker(fetch, on_done).start()
    """

    def __init__(
        self,
        worker_fn: Callable[[], Any],
        callback: Callable[[Any, Exception | None], None],
        root: tk.Misc | None = None,
    ):
        self._worker_fn = worker_fn
        self._callback = callback
        self._root = root

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def _run(self):
        try:
            result = self._worker_fn()
            self._schedule(result, None)
        except Exception as exc:
            self._schedule(None, exc)

    def _schedule(self, result, exc):
        """Deliver the callback on the Tkinter main thread if a root is known."""
        if self._root is not None:
            try:
                self._root.after(0, self._callback, result, exc)
                return
            except Exception:
                pass  # root may have been destroyed; fall through
        # Fallback: call directly (original behaviour, works when tkinter
        # happens to tolerate cross-thread calls on the current platform).
        self._callback(result, exc)