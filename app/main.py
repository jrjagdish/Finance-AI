from fastapi import FastAPI

from app.core.config import settings
from app.api.routes import (
    ai,
    dashboard,
    dev,
    entities,
    exceptions,
    health,
    ingestion,
    llm,
    match,
    normalize,
    reports,
)

app = FastAPI(title=settings.app_name)

app.include_router(health.router)
app.include_router(ingestion.router)
app.include_router(normalize.router)
app.include_router(match.router)
app.include_router(entities.router)
app.include_router(ai.router)
app.include_router(exceptions.router)
app.include_router(dashboard.router)
app.include_router(reports.router)
app.include_router(llm.router)
app.include_router(dev.router)
