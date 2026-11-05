import asyncio
import time
from enum import Enum
from typing import Callable, Any, Optional
import functools
import structlog

logger = structlog.get_logger(__name__)

class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreakerError(Exception):
    def __init__(self, name: str, remaining_seconds: float):
        super().__init__(f"Circuit breaker '{name}' is OPEN. Retry in {remaining_seconds:.1f}s")
        self.name = name
        self.remaining_seconds = remaining_seconds

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.half_open_calls = 0
        self.half_open_successes = 0
        self._lock = asyncio.Lock()

    async def __call__(self, func: Callable, *args, **kwargs) -> Any:
        await self._pre_call()
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            if not isinstance(e, CircuitBreakerError):
                await self._on_failure()
            raise

    async def _pre_call(self):
        async with self._lock:
            now = time.time()
            if self.state == CircuitBreakerState.CLOSED:
                return

            if self.state == CircuitBreakerState.OPEN:
                elapsed = now - (self.last_failure_time or 0.0)
                if elapsed >= self.recovery_timeout:
                    logger.info("Circuit breaker transitioning to HALF_OPEN", name=self.name)
                    self.state = CircuitBreakerState.HALF_OPEN
                    self.half_open_calls = 1
                    self.half_open_successes = 0
                    return
                raise CircuitBreakerError(self.name, self.recovery_timeout - elapsed)

            if self.state == CircuitBreakerState.HALF_OPEN:
                if self.half_open_calls < self.half_open_max_calls:
                    self.half_open_calls += 1
                    return
                raise CircuitBreakerError(self.name, 0.5)

    async def _on_success(self):
        async with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                self.failure_count = 0
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.half_open_successes += 1
                if self.half_open_successes >= self.half_open_max_calls:
                    logger.info("Circuit breaker recovered: HALF_OPEN -> CLOSED", name=self.name)
                    self.state = CircuitBreakerState.CLOSED
                    self.failure_count = 0
                    self.half_open_calls = 0
                    self.half_open_successes = 0

    async def _on_failure(self):
        async with self._lock:
            self.last_failure_time = time.time()
            if self.state == CircuitBreakerState.CLOSED:
                self.failure_count += 1
                logger.warn("Circuit breaker failure recorded", name=self.name, failures=self.failure_count)
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitBreakerState.OPEN
                    logger.error("Circuit breaker TRIPPED to OPEN", name=self.name)
            elif self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                logger.error("Circuit breaker probe failed: HALF_OPEN -> OPEN", name=self.name)

    async def reset(self):
        async with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0
            self.half_open_calls = 0
            self.half_open_successes = 0

def circuit_breaker(name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
    cb = CircuitBreaker(name=name, failure_threshold=failure_threshold, recovery_timeout=recovery_timeout)
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb(func, *args, **kwargs)
        wrapper.circuit_breaker = cb
        return wrapper
    return decorator
