from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    app_name: str = "Parva"
    debug: bool = False

    # LiteLLM (OpenAI-compatible)
    litellm_base_url: str = "http://litellm:4000/v1"
    litellm_api_key: str = "sk-parva"
    default_chat_model: str = "gpt-4o"
    default_image_model: str = "dall-e-3"

    # Postgres
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_user: str = "parva"
    postgres_password: str = "parva"
    postgres_db: str = "parva"

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # MinIO
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "parva"
    minio_secret_key: str = "parvasecret"
    minio_bucket: str = "parva-files"
    minio_secure: bool = False

    # Docker execution
    executor_image: str = "parva-executor:latest"
    executor_network: str = "parva-net"
    executor_workspace_base: str = "/var/parva/workspaces"
    executor_idle_timeout_seconds: int = 1800  # 30 min idle -> reclaim
    executor_memory_limit: str = "512m"
    executor_cpu_limit: float = 1.0

    # Auth
    jwt_secret: str = "parva-dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 24

    # WebSocket / Notifications
    ws_heartbeat_interval: int = 30

    model_config = {"env_prefix": "PARVA_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
