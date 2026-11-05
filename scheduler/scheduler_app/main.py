from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog

try:
    from .routes import router, node_mgr, workload_sched, fail_detector
except ImportError:
    from routes import router, node_mgr, workload_sched, fail_detector

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../shared/python")))
from common.health import HealthChecker, create_health_router

logger = structlog.get_logger(__name__)

health_checker = HealthChecker(service_name="workload-scheduler")
health_checker.register("cluster_50_nodes", lambda: len(node_mgr.nodes) >= 50)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Workload Rescheduler & Fault Tolerance Engine across 50 nodes...")
    # Initialize the 50 heterogeneous nodes cluster
    await node_mgr.initialize(node_count=50)

    # Seed initial heartbeats
    for node_id in node_mgr.nodes:
        fail_detector.record_heartbeat(node_id)

    # Start Phi Accrual Failure Detector loop
    await fail_detector.start()
    yield
    await fail_detector.stop()
    logger.info("Workload Scheduler stopped.")

app = FastAPI(
    title="Highly Available AI Microservices - Workload Rescheduler",
    description="Automated Workload Rescheduling and Phi-Accrual Fault Tolerance Engine across 50-Node Distributed AI Environments.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(create_health_router(health_checker))
app.mount("/metrics", make_asgi_app())
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8087, reload=True)
