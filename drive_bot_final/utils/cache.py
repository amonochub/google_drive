import time
from typing import Any, Optional

class TTLCache:
    def __init__(self, ttl_seconds: int):
        self.ttl = ttl_seconds
        self.store: dict[Any, tuple[Any, float]] = {}  # key -> (data, timestamp)
    def get(self, key: Any) -> Optional[Any]:
        data, ts = self.store.get(key, (None, 0))
        if time.time() - ts < self.ttl:
            return data
        return None
    def set(self, key: Any, data: Any):
        self.store[key] = (data, time.time())
    def invalidate(self, key: Any = None):
        if key:
            self.store.pop(key, None)
        else:
            self.store.clear() 