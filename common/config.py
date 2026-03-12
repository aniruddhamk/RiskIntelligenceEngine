"""
Centralized application configuration using pydantic-settings.
All environment variables are loaded from .env file.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Application
    app_env: str = Field("development", description="Environment (development/staging/production)")
    secret_key: str = Field("change-me-in-production", description="JWT secret key")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Database
    database_url: str = Field("postgresql+asyncpg://aml_user:aml_pass@localhost:5432/aml_db")
    database_url_sync: str = Field("postgresql://aml_user:aml_pass@localhost:5432/aml_db")

    # Redis
    redis_url: str = Field("redis://localhost:6379/0")

    # Kafka
    kafka_bootstrap_servers: str = Field("localhost:9092")
    kafka_group_id: str = Field("aml-consumer-group")

    # Neo4j
    neo4j_uri: str = Field("bolt://localhost:7687")
    neo4j_user: str = Field("neo4j")
    neo4j_password: str = Field("amlpassword")

    # Internal service URLs
    feature_service_url: str = Field("http://localhost:8003")
    rule_service_url: str = Field("http://localhost:8004")
    ml_service_url: str = Field("http://localhost:8005")
    graph_service_url: str = Field("http://localhost:8006")
    aggregation_service_url: str = Field("http://localhost:8007")
    alert_service_url: str = Field("http://localhost:8008")

    # ML Model
    model_version: str = Field("AML_GB_v4.1")
    model_path: str = Field("/app/models/saved/aml_model.joblib")

    # Risk thresholds
    risk_low_max: int = 30
    risk_medium_max: int = 60
    risk_high_max: int = 80

    # Logging
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor used as FastAPI dependency."""
    return Settings()
