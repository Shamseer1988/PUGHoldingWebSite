# PUG Holding - Backend (FastAPI)

Phase 1 foundation for the Paris United Group Holding backend.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- SQLAlchemy 2 ORM
- Alembic migrations
- PostgreSQL
- Pydantic v2 settings

## Local setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env with your local PostgreSQL credentials
```

## Run the API

```bash
python run.py
# or
uvicorn app.main:app --reload
```

The API is then served at:

- Root:        http://localhost:8000/
- Swagger UI:  http://localhost:8000/docs
- ReDoc:       http://localhost:8000/redoc
- Health:      http://localhost:8000/api/v1/health
- Liveness:    http://localhost:8000/api/v1/health/live

## Database migrations

```bash
alembic upgrade head                                   # apply migrations
alembic revision --autogenerate -m "describe change"   # author a new revision
alembic downgrade -1                                   # revert one revision
```

## Seed data

```bash
python -m app.scripts.seed_users
```

Creates baseline roles, permissions, and the five seed accounts
(see [`docs/setup-guide.md`](../docs/setup-guide.md)). Idempotent.

## Tests

```bash
pytest -q
```

## Layout

```
backend/
  app/
    api/            # FastAPI routers
    auth/           # Auth (Phase 2)
    models/         # SQLAlchemy models
    schemas/        # Pydantic schemas
    services/       # Business logic (later phases)
    utils/          # Shared helpers
    uploads/        # Runtime file storage (gitignored)
    website_admin/  # CMS modules (Phase 5)
    hr_ats/         # HR ATS modules (Phase 7+)
    ai/             # Azure OpenAI integration (Phase 13/17)
    core/           # Config + DB engine
    main.py         # FastAPI app factory
  migrations/       # Alembic
  tests/
  requirements.txt
  .env.example
  run.py
```
