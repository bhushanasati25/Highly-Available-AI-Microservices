from fastapi import FastAPI
from prometheus_client import make_asgi_app
import structlog

try:
    from .routes import router
except ImportError:
    from routes import router

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
from common.health import HealthChecker, create_health_router

logger = structlog.get_logger(__name__)

health_checker = HealthChecker(service_name="model-manager")
health_checker.register("model_registry", lambda: True)

app = FastAPI(
    title="Highly Available AI Microservices - Model Manager",
    description="Model Registry, semantic versioning, artifact deduplication and deployment service.",
    version="1.0.0",
)

app.include_router(create_health_router(health_checker))
app.mount("/metrics", make_asgi_app())
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8085, reload=True)
