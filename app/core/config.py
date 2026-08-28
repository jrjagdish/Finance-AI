from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "AI Finance Controller"
    debug: bool = True

    database_url: str = "postgresql+psycopg2://finance:finance@localhost:5432/finance_ai"

    storage_dir: str = "./storage"

    # No auth in v1 — every record is written under this single tenant.
    default_tenant_id: str = "default"

    # Deterministic matching engine defaults (overridable per-tenant via matching_rules).
    default_amount_tolerance: float = 1.0
    default_date_window_days: int = 3
    max_aggregation_group_size: int = 4

    # Groq / LLM (AI exception resolver) — left unset until the user provides a key.
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    ai_high_confidence: float = 0.85
    ai_medium_confidence: float = 0.5


settings = Settings()
