from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Finance Controller"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://finance:finance@localhost:5432/finance_ai"
    redis_url: str = "redis://localhost:6379/0"

    storage_dir: str = "./storage"

    # No auth in v1 — every record is written under this single tenant.
    default_tenant_id: str = "default"


settings = Settings()
