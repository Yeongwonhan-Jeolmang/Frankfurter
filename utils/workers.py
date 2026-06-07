"""
Background worker that keeps the GUI responsive while fetching data.
"""

import threading
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
    ):
        self._worker_fn = worker_fn
        self._callback = callback

    def start(self):
        t = threading.Thread(target=self._run, daemon=True)
        t.start()
        return t

    def _run(self):
        try:
            result = self._worker_fn()
            self._callback(result, None)
        except Exception as exc:
            self._callback(None, exc)