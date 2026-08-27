from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import health, ingestion

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(ingestion.router)
