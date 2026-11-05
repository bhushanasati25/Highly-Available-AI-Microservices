from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    service_name: str = "hams-service"
    host: str = "0.0.0.0"
    port: int = 8080
    environment: str = "dev"
    log_level: str = "INFO"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: Optional[str] = None

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "hams"
    postgres_user: str = "hams"
    postgres_password: str = "hams_dev_password"

    # RabbitMQ
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"

    # Upstream Microservice Endpoints
    data_ingestion_grpc: str = "localhost:50051"
    preprocessing_grpc: str = "localhost:50052"
    storage_manager_url: str = "http://localhost:8083"
    training_orchestrator_url: str = "http://localhost:8084"
    model_manager_url: str = "http://localhost:8085"
    monitoring_url: str = "http://localhost:8086"
    scheduler_url: str = "http://localhost:8087"

    model_config = SettingsConfigDict(
        env_prefix="HAMS_",
        case_sensitive=False,
        extra="allow"
    )
