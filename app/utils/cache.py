import time

class SimpleCache:
    def __init__(self, default_ttl_seconds: int = 300):
        self._store = {}
        self.default_ttl = default_ttl_seconds

    def get(self, key: str):
        record = self._store.get(key)
        if not record:
            return None
        val, expiry = record
        if time.time() > expiry:
            del self._store[key]
            return None
        return val

    def set(self, key: str, value, ttl: int = None):
        expiry = time.time() + (ttl or self.default_ttl)
        self._store[key] = (value, expiry)

    def clear(self):
        self._store.clear()

catalogue_cache = SimpleCache(default_ttl_seconds=300)