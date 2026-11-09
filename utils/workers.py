"""
Background worker that keeps the GUI responsive while fetching data.

Tkinter is not thread-safe: calling *any* widget method (including
``after()``) from a worker thread can raise ``RuntimeError: main thread is
not in main loop`` or silently corrupt state on non-threaded Tcl builds.
Results are therefore pushed onto a thread-safe queue that a single
``after()`` loop running on the GUI thread drains and dispatches.
"""

import queue
import threading
import tkinter as tk
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

# One shared, bounded pool instead of a brand-new thread per request.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="frankfurter-io")


class _Dispatcher:
    """Drains worker results on the Tk main thread."""

    POLL_MS = 15

    _instances: dict[int, "_Dispatcher"] = {}
    _lock = threading.Lock()

    def __init__(self, root: tk.Misc):
        self._root = root
        self._q: queue.SimpleQueue[tuple[Callable, Any, Any]] = queue.SimpleQueue()
        self._alive = True
        self._root.after(self.POLL_MS, self._poll)

    @classmethod
    def for_root(cls, root: tk.Misc) -> "_Dispatcher":
        # Must be called from the GUI thread (AsyncWorker.start does so).
        key = id(root)
        with cls._lock:
            d = cls._instances.get(key)
            if d is None or not d._alive:
                d = cls(root)
                cls._instances[key] = d
            return d

    def post(self, callback, result, exc) -> None:
        """Thread-safe: may be called from any thread."""
        self._q.put((callback, result, exc))

    def _poll(self) -> None:
        try:
            while True:
                cb, result, exc = self._q.get_nowait()
                try:
                    cb(result, exc)
                except Exception as e:  # never let one bad callback kill the loop
                    try:
                        self._root.report_callback_exception(
                            type(e), e, e.__traceback__
                        )
                    except Exception:
                        pass
        except queue.Empty:
            pass
        try:
            self._root.after(self.POLL_MS, self._poll)
        except (tk.TclError, RuntimeError):
            # Root destroyed — stop polling and drop pending callbacks.
            self._alive = False


class AsyncWorker:
    """
    Runs a callable in a background thread and delivers the result (or
    exception) back to the GUI thread via a callback.

    Usage::

        def fetch():
            return client.get_latest_rates("USD")

        def on_done(result, error):
            if error:
                show_error(str(error))
            else:
                update_table(result)

        AsyncWorker(fetch, on_done, root=widget.winfo_toplevel()).start()
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
        self._dispatcher: _Dispatcher | None = None

    def start(self):
        if self._root is not None:
            # Created on the GUI thread, before the work is submitted.
            self._dispatcher = _Dispatcher.for_root(self._root)
        return _POOL.submit(self._run)

    def _run(self):
        try:
            result = self._worker_fn()
            self._schedule(result, None)
        except Exception as exc:
            self._schedule(None, exc)

    def _schedule(self, result, exc):
        """Deliver the callback on the Tkinter main thread if a root is known."""
        if self._dispatcher is not None:
            self._dispatcher.post(self._callback, result, exc)
            return
        # No root given: caller opted into a direct (worker-thread) callback.
        self._callback(result, exc)
