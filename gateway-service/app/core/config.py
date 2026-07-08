from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    app_name: str = "clan-api-gateway"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me-in-production-use-32-chars"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/api_gateway"
    database_pool_size: int = 20
    database_max_overflow: int = 40

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """
        SQLAlchemy async needs the asyncpg driver. Render's Internal Database URL
        is a bare `postgresql://...`, which SQLAlchemy maps to psycopg2 (not
        installed here) — normalize it to `postgresql+asyncpg://...` so the
        connection string works as pasted.
        """
        if v.startswith("postgresql+"):
            return v
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+asyncpg://" + v[len(prefix):]
        return v

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_algorithm: str = "RS256"
    jwt_public_key_path: str = "/etc/gateway/jwt/public.pem"
    jwt_private_key_path: str = "/etc/gateway/jwt/private.pem"
    jwt_access_token_expire_minutes: int = 60
    jwt_issuer: str = "https://auth.example.com"
    jwt_audience: str = "api-gateway"
    jwks_uri: str = "https://auth.example.com/.well-known/jwks.json"
    jwks_cluster: str = "jwks_cluster"

    # Envoy xDS
    envoy_admin_url: str = "http://localhost:9901"
    xds_transport_api_version: str = "V3"
    cds_refresh_delay: str = "10s"
    lds_refresh_delay: str = "30s"
    rds_refresh_delay: str = "5s"

    # Gateway
    gateway_domain: str = "api.example.com"

    # Rate limiting defaults (per-tenant overrides live in DB)
    default_rate_limit_rps: int = 100
    default_rate_limit_burst: int = 200

    # Internal sync key — clan-platform-domain-be sends this when calling /sync/*
    internal_api_key: str = "internal-secret-key"

    # Observability
    metrics_enabled: bool = True
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
