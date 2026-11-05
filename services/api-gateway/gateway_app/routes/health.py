from fastapi import APIRouter
from typing import Dict, Any
import httpx
try:
    from ..config import settings
except ImportError:
    from config import settings

router = APIRouter(tags=["Health Aggregation"])

@router.get("/api/v1/system/health")
async def system_health_overview() -> Dict[str, Any]:
    services = {
        "storage-manager": f"{settings.storage_manager_url}/health",
        "training-orchestrator": f"{settings.training_orchestrator_url}/health",
        "model-manager": f"{settings.model_manager_url}/health",
        "monitoring": f"{settings.monitoring_url}/health",
        "scheduler": f"{settings.scheduler_url}/health",
    }

    results = {}
    overall = True

    async with httpx.AsyncClient(timeout=2.0) as client:
        for name, url in services.items():
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    results[name] = {"status": "UP", "details": resp.json()}
                else:
                    results[name] = {"status": "DEGRADED", "http_code": resp.status_code}
                    overall = False
            except Exception as e:
                results[name] = {"status": "UNREACHABLE", "error": str(e)}
                # In development/test mode keep cluster alive
                overall = False

    return {
        "status": "HEALTHY" if overall else "DEGRADED",
        "timestamp": 1700000000.0,
        "services": results
    }
