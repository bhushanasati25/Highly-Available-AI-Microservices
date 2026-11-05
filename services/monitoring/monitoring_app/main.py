import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog

try:
    from .routes import router, service_health, heartbeat_monitor
except ImportError:
    from routes import router, service_health, heartbeat_monitor

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
from common.health import HealthChecker, create_health_router

logger = structlog.get_logger(__name__)

health_checker = HealthChecker(service_name="monitoring")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Monitoring & Telemetry Service...")
    # Seed 50 simulated cluster nodes into heartbeat monitor
    for i in range(1, 51):
        heartbeat_monitor.record_heartbeat(
            node_id=f"node-{i:02d}",
            cpu=15.0 + (i % 25),
            mem=30.0 + (i % 20),
            gpu=2 if (i % 4 == 0) else 0
        )

    # Background health checker task
    async def loop():
        while True:
            try:
                await service_health.check_all()
                heartbeat_monitor.scan_dead_nodes()
            except Exception:
                pass
            await asyncio.sleep(5.0)

    task = asyncio.create_task(loop())
    yield
    task.cancel()
    logger.info("Monitoring Service stopped.")

app = FastAPI(
    title="Highly Available AI Microservices - Monitoring & Telemetry",
    description="Centralized heartbeat tracker, node failure detector, and Prometheus metrics exporter.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(create_health_router(health_checker))
app.mount("/metrics", make_asgi_app())
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8086, reload=True)
