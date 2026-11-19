import threading
import time
from typing import Any, Optional


class SimpleCache:
    """Thread-safe in-memory TTL cache for diagnostic centre catalogue lookups."""

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self._ttl_seconds
        with self._lock:
            self._store[key] = (time.monotonic() + ttl, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Invalidate all cached catalogue entries."""
        with self._lock:
            self._store.clear()


catalogue_cache = SimpleCache(ttl_seconds=300)
