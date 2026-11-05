import time
from collections import defaultdict
from fastapi import Request, Response, status
import structlog

logger = structlog.get_logger(__name__)

class SlidingWindowRateLimiter:
    def __init__(self, limit_per_minute: int = 120):
        self.limit = limit_per_minute
        self.window_seconds = 60.0
        self._requests = defaultdict(list)

    def is_allowed(self, client_id: str) -> tuple[bool, int, float]:
        now = time.time()
        window_start = now - self.window_seconds

        # Filter out timestamps outside window
        timestamps = [ts for ts in self._requests[client_id] if ts > window_start]
        self._requests[client_id] = timestamps

        if len(timestamps) >= self.limit:
            oldest = timestamps[0]
            retry_after = round(self.window_seconds - (now - oldest), 1)
            return False, 0, max(0.5, retry_after)

        self._requests[client_id].append(now)
        remaining = self.limit - len(self._requests[client_id])
        return True, remaining, 0.0

rate_limiter_instance = SlidingWindowRateLimiter()

async def rate_limit_middleware(request: Request, call_next):
    # Skip health and internal checks
    if request.url.path in ["/health", "/ready", "/metrics"]:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown_client"
    allowed, remaining, retry_after = rate_limiter_instance.is_allowed(client_ip)

    if not allowed:
        logger.warn("Rate limit exceeded", client_ip=client_ip, path=request.url.path)
        return Response(
            content='{"error": "Too Many Requests", "detail": "Rate limit exceeded"}',
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            media_type="application/json",
            headers={"Retry-After": str(int(retry_after))},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(rate_limiter_instance.limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response
