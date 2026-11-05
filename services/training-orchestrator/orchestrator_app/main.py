from contextlib import asynccontextmanager
from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog

try:
    from .orchestrator import orchestrator_instance
    from .routes import router
except ImportError:
    from orchestrator import orchestrator_instance
    from routes import router

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
from common.health import HealthChecker, create_health_router

logger = structlog.get_logger(__name__)

health_checker = HealthChecker(service_name="training-orchestrator")
health_checker.register("scheduler_engine", lambda: True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Training Orchestrator...")
    await orchestrator_instance.start()
    yield
    await orchestrator_instance.stop()
    logger.info("Training Orchestrator stopped.")

app = FastAPI(
    title="Highly Available AI Microservices - Training Orchestrator",
    description="Manages concurrent AI model training job queues, cluster resource balancing, and fault recovery.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(create_health_router(health_checker))
app.mount("/metrics", make_asgi_app())
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8084, reload=True)
