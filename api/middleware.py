import time
from collections import defaultdict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory per-IP rate limiter."""

    def __init__(self, app, calls: int = 120, period: int = 60):
        super().__init__(app)
        self._calls = calls
        self._period = period
        self._log: dict = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()

        self._log[ip] = [t for t in self._log[ip] if now - t < self._period]

        if len(self._log[ip]) >= self._calls:
            return Response(
                content='{"detail":"Rate limit exceeded — try again shortly"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(self._period)},
            )

        self._log[ip].append(now)
        return await call_next(request)
