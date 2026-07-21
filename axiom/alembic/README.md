# Database migrations (Alembic)

AXIOM runs on **SQLite by default** (a local file under `AXIOM_DATA_DIR`, no
setup needed — this is what the test suite uses) and on **PostgreSQL in
production**. Point it at Postgres with a single env var:

```
export AXIOM_DATABASE_URL=postgresql://user:pass@host:5432/axiom
```

`alembic/env.py` reads this same setting (`core.config.settings.database.sync_url`),
so migrations always target whatever database AXIOM itself is configured to use —
no separate migration URL to keep in sync.

## Commands

```bash
# Apply all migrations (creates the schema on a fresh DB)
alembic upgrade head

# Generate a new migration after changing storage/models.py
alembic revision --autogenerate -m "describe the change"

# Roll back the most recent migration
alembic downgrade -1
```

Postgres needs the drivers (commented in `requirements.txt`):
`pip install asyncpg psycopg2-binary`.

## docker-compose

`docker-compose up` starts a `postgres:16` service and wires the app to it via
`AXIOM_DATABASE_URL`. Run `alembic upgrade head` once against that database
(e.g. `docker compose exec axiom alembic upgrade head`) to create the schema.
