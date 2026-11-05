import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../shared/python")))

from common.config import Settings

class GatewayConfig(Settings):
    service_name: str = "api-gateway"
    port: int = 8080
    jwt_secret: str = "super-secret-jwt-key-for-ai-microservices-2026"
    jwt_algorithm: str = "HS256"
    token_expiry_seconds: int = 3600
    rate_limit_per_minute: int = 120

settings = GatewayConfig()
