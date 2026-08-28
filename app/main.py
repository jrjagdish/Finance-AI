import mimetypes
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.config import settings

# Some Windows Python installs map .js to text/plain in the registry, which
# StaticFiles inherits via mimetypes.guess_type — force the correct type so
# the frontend doesn't break under strict/nosniff serving in deployment.
mimetypes.add_type("application/javascript", ".js")
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

# Serves the vanilla HTML/JS frontend. Mounted last and at "/" so it acts as a
# fallback: API routes registered above still match first, everything else
# (including "/") falls through to the static files / index.html.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="static")
