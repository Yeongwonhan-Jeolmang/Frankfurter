"""
Background worker that keeps the GUI responsive while fetching data.

Qt widgets must only be touched from the GUI thread. Work runs on a shared
``ThreadPoolExecutor``; the result is handed back through a Qt signal on a
``QObject`` that lives in the GUI thread. Because the signal is emitted from
a different thread, Qt automatically queues it and the callback runs on the
GUI thread's event loop (no polling timer needed, unlike the Tk version).
"""

from __future__ import annotations

import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

from PyQt6.QtCore import QCoreApplication, QObject, pyqtSignal, pyqtSlot

# One shared, bounded pool instead of a brand-new thread per request.
_POOL = ThreadPoolExecutor(max_workers=8, thread_name_prefix="frankfurter-io")


class _Dispatcher(QObject):
    """Lives on the GUI thread; delivers worker results there."""

    deliver = pyqtSignal(object, object, object)

    _instance: "_Dispatcher | None" = None

    def __init__(self):
        super().__init__()
        self.deliver.connect(self._dispatch)

    @classmethod
    def instance(cls) -> "_Dispatcher":
        # Created lazily on first use, which always happens on the GUI thread
        # (AsyncWorker.start is only ever called from GUI code).
        if cls._instance is None:
            cls._instance = cls()
            app = QCoreApplication.instance()
            if app is not None:
                cls._instance.moveToThread(app.thread())
        return cls._instance

    @pyqtSlot(object, object, object)
    def _dispatch(self, callback, result, exc) -> None:
        try:
            callback(result, exc)
        except Exception:  # never let one bad callback take the app down
            traceback.print_exc()


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

        AsyncWorker(fetch, on_done).start()

    ``root`` is accepted (and ignored) for compatibility with the old Tk API.
    Pass ``gui_thread=False`` to receive the callback on the worker thread.
    """

    def __init__(
        self,
        worker_fn: Callable[[], Any],
        callback: Callable[[Any, Exception | None], None],
        root: Any = None,
        gui_thread: bool = True,
    ):
        self._worker_fn = worker_fn
        self._callback = callback
        self._dispatcher = _Dispatcher.instance() if gui_thread else None

    def start(self):
        return _POOL.submit(self._run)

    def _run(self):
        try:
            result = self._worker_fn()
        except Exception as exc:
            self._deliver(None, exc)
        else:
            self._deliver(result, None)

    def _deliver(self, result, exc):
        if self._dispatcher is not None:
            try:
                self._dispatcher.deliver.emit(self._callback, result, exc)
            except RuntimeError:
                pass  # application already shut down
            return
        self._callback(result, exc)


def shutdown() -> None:
    """Stop accepting work; don't block on in-flight HTTP requests."""
    _POOL.shutdown(wait=False, cancel_futures=True)
