"""Thread-backed async command queue for low-latency MT5 API calls."""

from __future__ import annotations

import queue
import threading
from concurrent.futures import Future
from typing import Any, Optional, Tuple


class AsyncMT5Engine:
    """Serializes MT5 function calls on one worker thread."""

    def __init__(self):
        self.command_queue: "queue.Queue[Tuple[str, tuple, dict, Future]]" = queue.Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._worker, name="AsyncMT5Engine", daemon=True)
        self.thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        if not self.running:
            return
        self.running = False
        self.command_queue.put(("__stop__", (), {}, Future()))
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=timeout)

    def _worker(self) -> None:
        try:
            import MetaTrader5 as mt5
        except Exception as exc:  # pragma: no cover - runtime environment specific
            while self.running:
                try:
                    _cmd, _args, _kwargs, fut = self.command_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not fut.done():
                    fut.set_exception(RuntimeError(f"MetaTrader5 import failed: {exc}"))
            return

        while self.running:
            try:
                cmd, args, kwargs, fut = self.command_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            if cmd == "__stop__":
                if not fut.done():
                    fut.set_result(None)
                continue

            try:
                result = getattr(mt5, cmd)(*args, **kwargs)
                if not fut.done():
                    fut.set_result(result)
            except Exception as exc:  # pragma: no cover - connector side effects
                if not fut.done():
                    fut.set_exception(exc)

    def call_async(self, cmd: str, *args: Any, **kwargs: Any) -> Future:
        future: Future = Future()
        self.command_queue.put((str(cmd), args, kwargs, future))
        return future

    def call(self, cmd: str, *args: Any, timeout: Optional[float] = None, **kwargs: Any) -> Any:
        future = self.call_async(cmd, *args, **kwargs)
        return future.result(timeout=timeout)
