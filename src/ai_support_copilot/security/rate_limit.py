import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    def __init__(self, limit_per_minute: int) -> None:
        self._limit = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def __call__(self, request: Request) -> None:
        client_host = request.client.host if request.client else "unknown"
        key = request.headers.get("x-tenant-id") or client_host
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self._limit:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        window.append(now)
