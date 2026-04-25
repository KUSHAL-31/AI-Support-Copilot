import hashlib
import json
import time
from typing import Any


class AsyncTTLCache:
    def __init__(self) -> None:
        self._data: dict[str, tuple[float, str]] = {}

    async def get_json(self, key: str) -> dict[str, Any] | None:
        item = self._data.get(key)
        if not item:
            return None
        expires_at, payload = item
        if expires_at < time.monotonic():
            self._data.pop(key, None)
            return None
        return json.loads(payload)

    async def set_json(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        self._data[key] = (time.monotonic() + ttl_seconds, json.dumps(value, default=str))

    @staticmethod
    def key(*parts: str) -> str:
        raw = ":".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


cache = AsyncTTLCache()
