# AI Finance Controller

Reconciles multi-source financial data (ledger, bank statements, payment gateway exports) using
deterministic rules first, then an LLM (Groq) to resolve remaining exceptions. See
[AI_Finance_Controller_PRD.md](AI_Finance_Controller_PRD.md) for the full product spec.

This repo is being built in milestones (see PRD section 9 + "Build Notes"). **Auth is deferred** —
v1 runs single-tenant, unauthenticated, against a `"default"` tenant.

## Milestone 1: Foundation (current)

- FastAPI app skeleton (`app/main.py`)
- PostgreSQL schema via SQLAlchemy models (`app/models/`) covering ingestion batches, raw records,
  entities, normalized records, matches, exceptions, matching rules, audit log, LLM call log
- Alembic migrations wired up
- Docker Compose for Postgres + Redis + the API
- `GET /health` endpoint (checks DB connectivity)

## Local setup

### Option A: Docker Compose (recommended)

```bash
docker compose up --build
```

API will be available at http://localhost:8000, docs at http://localhost:8000/docs.

### Option B: Run locally

```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt

cp .env.example .env
# start Postgres + Redis yourself, or: docker compose up db redis

alembic upgrade head
uvicorn app.main:app --reload
```

## Project layout

```
app/
  core/config.py       # settings (env-driven)
  db/                  # SQLAlchemy engine/session/base
  models/              # ORM models = the Postgres schema
  api/routes/          # FastAPI routers
alembic/               # DB migrations
```
