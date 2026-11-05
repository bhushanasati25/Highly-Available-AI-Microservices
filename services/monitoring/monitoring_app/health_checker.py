import asyncio
import time
from typing import Dict, List, Any
import httpx
import structlog

logger = structlog.get_logger(__name__)

class ServiceHealthMonitor:
    def __init__(self):
        self._endpoints: Dict[str, str] = {
            "api-gateway": "http://api-gateway:8080/health",
            "storage-manager": "http://storage-manager:8083/health",
            "training-orchestrator": "http://training-orchestrator:8084/health",
            "model-manager": "http://model-manager:8085/health",
            "scheduler": "http://scheduler:8087/health",
        }
        self._history: Dict[str, List[Dict[str, Any]]] = {s: [] for s in self._endpoints}
        self._consecutive_failures: Dict[str, int] = {s: 0 for s in self._endpoints}
        self.alerts: List[Dict[str, Any]] = []

    async def check_all(self):
        async with httpx.AsyncClient(timeout=2.0) as client:
            for name, url in self._endpoints.items():
                now = time.time()
                try:
                    resp = await client.get(url)
                    passed = (resp.status_code == 200)
                except Exception:
                    passed = False

                if passed:
                    self._consecutive_failures[name] = 0
                else:
                    self._consecutive_failures[name] += 1
                    if self._consecutive_failures[name] >= 3:
                        alert = {
                            "service": name,
                            "severity": "CRITICAL",
                            "message": f"Service {name} failed 3 consecutive health checks",
                            "timestamp": now,
                        }
                        self.alerts.append(alert)
                        logger.error("Health Alert Raised", **alert)

                self._history[name].append({
                    "timestamp": now,
                    "status": "PASS" if passed else "FAIL"
                })
                # keep recent 50 samples
                if len(self._history[name]) > 50:
                    self._history[name].pop(0)

    def get_service_statuses(self) -> Dict[str, Any]:
        return {
            name: {
                "healthy": (self._consecutive_failures[name] == 0),
                "consecutive_failures": self._consecutive_failures[name],
                "last_status": self._history[name][-1]["status"] if self._history[name] else "UNKNOWN",
            }
            for name in self._endpoints
        }
