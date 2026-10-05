"""
Rate limiting: interface + in-memory implementation.

Deliberately mirrors app/integrations/*/provider.py's shape (an interface,
one concrete implementation, a factory) so a future distributed backend
(e.g. Redis-backed, for multi-process deployments) is a new class + a
factory branch - not a rewrite of every caller. See
docs/decisions/0004-auth-rate-limiting.md for the full rationale and the
current implementation's known limitation (per-process state only).
"""

import math
import threading
import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque


class RateLimiter(ABC):
    """Interface every rate-limiting backend must implement."""

    @abstractmethod
    def check(self, key: str, max_requests: int, window_seconds: float) -> tuple[bool, int]:
        """
        Records one attempt for `key` and reports whether it's allowed under
        a `max_requests` per `window_seconds` sliding window.

        Returns (allowed, retry_after_seconds). `retry_after_seconds` is only
        meaningful when `allowed` is False: seconds until the oldest request
        counted in the current window ages out and a new one would be let
        through. Always a positive integer, suitable for a `Retry-After`
        header as-is.
        """

    @abstractmethod
    def reset(self) -> None:
        """Clears all tracked state. Test-only: production code never calls this."""


class InMemoryRateLimiter(RateLimiter):
    """
    Sliding-window-log limiter, in-process memory only - no external
    storage. A `deque` of monotonic timestamps is kept per key; each check
    drops timestamps older than the window, then allows the request only if
    fewer than `max_requests` remain.

    Known limitation (by design for now - see the ADR): state lives in this
    process's memory only. Running multiple worker processes/replicas gives
    each its own independent counters, so the *effective* limit multiplies
    by the process count. Acceptable for a single-process deployment; a
    distributed backend (e.g. Redis) would replace this class, not its
    callers - see `RateLimiter` above.

    Thread-safe: FastAPI runs sync path operation functions (like
    register/login) in a worker threadpool, so concurrent requests can call
    `check()` from different threads at once - the lock keeps the
    read-prune-compare-append sequence atomic.
    """

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, max_requests: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            cutoff = now - window_seconds
            while hits and hits[0] <= cutoff:
                hits.popleft()

            if len(hits) >= max_requests:
                retry_after = max(1, math.ceil(hits[0] + window_seconds - now))
                return False, retry_after

            hits.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
