import threading
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit_per_minute: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._events[key]
            while q and now - q[0] > 60.0:
                q.popleft()
            if len(q) >= limit_per_minute:
                return False
            q.append(now)
            return True


class ConnectionSemaphoreRegistry:
    def __init__(self, max_per_connection: int):
        self._max = max(1, max_per_connection)
        self._lock = threading.Lock()
        self._sems: dict[str, threading.BoundedSemaphore] = {}

    def get(self, connection_id: str) -> threading.BoundedSemaphore:
        with self._lock:
            sem = self._sems.get(connection_id)
            if sem is None:
                sem = threading.BoundedSemaphore(self._max)
                self._sems[connection_id] = sem
            return sem


rate_limiter = SlidingWindowRateLimiter()
