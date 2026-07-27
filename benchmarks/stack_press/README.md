# Stack press — Phzyx vs SQLAlchemy vs Django (Postgres 18)

Real HTTP + ORM + Postgres load on OrbStack, not micro-SQL toys.

## Prerequisites

```bash
./scripts/dbs/up.sh postgres   # needs phzyx-pg-18 on :5518
```

Create DBs (once):

```bash
for db in bench_phzyx bench_sa bench_django; do
  docker exec phzyx-pg-18 psql -U phzyx -d phzyx -tc "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 \
    || docker exec phzyx-pg-18 psql -U phzyx -d phzyx -c "CREATE DATABASE $db"
done
```

Deps (venv):

```bash
uv pip install sqlalchemy greenlet asyncpg django 'psycopg[binary]' httpx 'uvicorn[standard]'
```

## Run

```bash
export PYTHONPATH=.
uv run python benchmarks/stack_press/run_press.py --n 200 --concurrency 25
```

Writes:

- `benchmarks/stack_press/RESULTS.md`
- `benchmarks/stack_press/results/latest.json`

## Apps

| Stack | Port | Serve |
|-------|------|--------|
| Phzyx + FastAPI **async** | 9201 | Uvicorn · **N workers** (asyncio per process) |
| SQLAlchemy 2 + FastAPI **async** | 9202 | Uvicorn · **N workers** |
| Django **sync WSGI** | 9203 | Gunicorn `gthread` · **N workers × T threads** |

Same REST contract: see `SPEC.md`.

**Fair multi-process:** all stacks share `BENCH_WORKERS` (default 2–4). Async is not left on one worker while Django multiplies processes. Inside a process, async uses the event loop; Django uses threads (`BENCH_THREADS`, default 4).

Deps: also `gunicorn`.

## Manual deploy (keep servers up)

```bash
export BENCH_WORKERS=4
export BENCH_THREADS=4
# async stacks — same worker count
uv run uvicorn benchmarks.stack_press.apps.phzyx_app.main:app --port 9201 --workers 4
uv run uvicorn benchmarks.stack_press.apps.sqlalchemy_app.main:app --port 9202 --workers 4
# sync Django — same workers, threads for sync parallelization
uv run gunicorn benchmarks.stack_press.apps.django_app.wsgi:application \
  --bind 127.0.0.1:9203 --worker-class gthread --workers 4 --threads 4
```
