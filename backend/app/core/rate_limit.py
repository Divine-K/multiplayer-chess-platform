"""A small in-memory sliding-window limiter, enough for the single API process this app runs as."""

import time
from collections import deque
from collections.abc import Callable
from threading import Lock

_SWEEP_THRESHOLD = 10_000


class SlidingWindowLimiter:
    def __init__(
        self, limit: int, window_seconds: float, clock: Callable[[], float] = time.monotonic
    ) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()  # synchronous routes run on several threads

    def retry_after(self, key: str) -> float:
        """Record an attempt. Returns 0 if allowed, else how many seconds until one would be."""
        with self._lock:
            now = self._clock()
            if len(self._hits) >= _SWEEP_THRESHOLD:
                self._forget_expired(now)
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self._window:
                hits.popleft()
            if len(hits) >= self._limit:
                return self._window - (now - hits[0])
            hits.append(now)
            return 0

    def _forget_expired(self, now: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or now - hits[-1] >= self._window]:
            del self._hits[key]
