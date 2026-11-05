import time
from typing import Callable, Dict, Any, Awaitable, Optional
from fastapi import APIRouter, Response, status
import inspect

class HealthChecker:
    """
    Cloud-Native 3-Tier Health Checker compliant with Kubernetes probe standards:
    - Liveness (/healthz): verifies the process is responsive and not deadlocked.
    - Readiness (/readyz): verifies downstream dependencies are healthy and able to accept traffic.
    - Startup (/startupz): verifies heavy initialization / model caching has completed.
    Also provides legacy /health and /ready routes for backward compatibility.
    """
    def __init__(self, service_name: str):
        self.service_name = service_name
        self._readiness_checks: Dict[str, Callable[[], Awaitable[bool] | bool]] = {}
        self._liveness_checks: Dict[str, Callable[[], Awaitable[bool] | bool]] = {}
        self._startup_checks: Dict[str, Callable[[], Awaitable[bool] | bool]] = {}
        self.start_time = time.time()
        self.initialized = True

    def register(self, name: str, check_fn: Callable[[], Awaitable[bool] | bool]):
        """Legacy registration defaults to readiness check."""
        self._readiness_checks[name] = check_fn

    def register_readiness(self, name: str, check_fn: Callable[[], Awaitable[bool] | bool]):
        self._readiness_checks[name] = check_fn

    def register_liveness(self, name: str, check_fn: Callable[[], Awaitable[bool] | bool]):
        self._liveness_checks[name] = check_fn

    def register_startup(self, name: str, check_fn: Callable[[], Awaitable[bool] | bool]):
        self._startup_checks[name] = check_fn

    async def _evaluate_checks(self, checks_dict: Dict[str, Callable]) -> tuple[Dict[str, str], bool]:
        results = {}
        overall_healthy = True
        for name, fn in checks_dict.items():
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
        return results, overall_healthy

    async def check_liveness(self) -> Dict[str, Any]:
        results, healthy = await self._evaluate_checks(self._liveness_checks)
        return {
            "status": "alive" if healthy else "deadlocked",
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
        }

    async def check_readiness(self) -> Dict[str, Any]:
        results, healthy = await self._evaluate_checks(self._readiness_checks)
        return {
            "status": "ready" if healthy else "not_ready",
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
        }

    async def check_startup(self) -> Dict[str, Any]:
        results, healthy = await self._evaluate_checks(self._startup_checks)
        return {
            "status": "started" if (healthy and self.initialized) else "initializing",
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
        }

    async def run_checks(self) -> Dict[str, Any]:
        # Legacy aggregated checks
        results, healthy = await self._evaluate_checks(self._readiness_checks)
        return {
            "status": "healthy" if healthy else "unhealthy",
            "service": self.service_name,
            "uptime_seconds": round(time.time() - self.start_time, 2),
            "checks": results,
        }

def create_health_router(checker: HealthChecker) -> APIRouter:
    router = APIRouter(tags=["Health & Probes"])

    # Kubernetes Liveness Probe
    @router.get("/healthz")
    async def liveness_probe(response: Response):
        res = await checker.check_liveness()
        if res["status"] != "alive":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    # Kubernetes Readiness Probe
    @router.get("/readyz")
    async def readiness_probe(response: Response):
        res = await checker.check_readiness()
        if res["status"] != "ready":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    # Kubernetes Startup Probe
    @router.get("/startupz")
    async def startup_probe(response: Response):
        res = await checker.check_startup()
        if res["status"] != "started":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    # Legacy & Ingress Endpoints
    @router.get("/health")
    async def get_health(response: Response):
        res = await checker.run_checks()
        if res["status"] != "healthy":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    @router.get("/ready")
    async def get_ready(response: Response):
        res = await checker.check_readiness()
        if res["status"] != "ready":
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return res

    return router
