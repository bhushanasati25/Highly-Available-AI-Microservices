import time
from typing import Callable, Dict, Any, Awaitable
from fastapi import APIRouter, Response, status
import inspect

class HealthChecker:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._checks: Dict[str, Callable[[], Awaitable[bool] | bool]] = {}
        self.start_time = time.time()

    def register(self, name: str, check_fn: Callable[[], Awaitable[bool] | bool]):
        self._checks[name] = check_fn

    async def run_checks(self) -> Dict[str, Any]:
        results = {}
        overall_healthy = True

        for name, fn in self._checks.items():
            try:
                if inspect.iscoroutinefunction(fn):
                    passed = await fn()
                else:
                    passed = fn()
            except Exception:
                passed = False

            results[name] = "pass" if passed else "fail"
            if not passed:
                overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
        }

def create_health_router(checker: HealthChecker) -> APIRouter:
    router = APIRouter(tags=["Health"])

    @router.get("/health")
    @router.get("/ready")
    async def get_health(response: Response):
        res = await checker.run_checks()
        if res["status"] != "healthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    return router
