from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
import structlog

try:
    from .config import settings
    from .middleware.request_logger import request_logger_middleware
    from .middleware.rate_limiter import rate_limit_middleware
    from .middleware.auth import auth_middleware, create_access_token
    from .services.service_discovery import service_registry
    from .routes import ingestion, training, models, health
except ImportError:
    from config import settings
    from middleware.request_logger import request_logger_middleware
    from middleware.rate_limiter import rate_limit_middleware
    from middleware.auth import auth_middleware, create_access_token
    from services.service_discovery import service_registry
    from routes import ingestion, training, models, health

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))
from common.health import HealthChecker, create_health_router

logger = structlog.get_logger(__name__)

health_checker = HealthChecker(service_name="api-gateway")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting API Gateway...", port=settings.port, env=settings.environment)
    # Register internal default downstream service URLs
    await service_registry.register("training-orchestrator", settings.training_orchestrator_url)
    await service_registry.register("model-manager", settings.model_manager_url)
    await service_registry.register("monitoring", settings.monitoring_url)
    await service_registry.register("scheduler", settings.scheduler_url)
    yield
    logger.info("API Gateway shutdown complete.")

app = FastAPI(
    title="Highly Available AI Microservices - API Gateway",
    description="Unified API Gateway providing secure routing, rate limiting, and health aggregation for distributed AI microservices.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Middlewares
app.middleware("http")(request_logger_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(auth_middleware)

# Health & Metrics
app.include_router(create_health_router(health_checker))
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# Authentication token generator endpoint for dev / testing
@app.post("/api/v1/auth/token", tags=["Authentication"])
async def obtain_token(username: str = "admin"):
    token = create_access_token({"sub": username, "roles": ["admin", "developer"]})
    return {"access_token": token, "token_type": "bearer"}

# Service Routes
app.include_router(ingestion.router)
app.include_router(training.router)
app.include_router(models.router)
app.include_router(health.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
