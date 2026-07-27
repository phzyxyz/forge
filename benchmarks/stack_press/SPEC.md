# Stack press — identical CRUD API

**Target DB:** PostgreSQL 18 on OrbStack (`phzyx-pg-18`, host port **5518**)

**Workload:** same REST shape on all three stacks.

| Method | Path | Body / notes |
|--------|------|----------------|
| `POST` | `/items` | `{"name": str, "notes": str\|null}` → create, return row with `id` |
| `GET` | `/items/{id}` | single row or 404 |
| `GET` | `/items?limit=N` | list, default 50, max 200 |
| `PUT` | `/items/{id}` | partial update name/notes |
| `DELETE` | `/items/{id}` | delete |
| `GET` | `/health` | `{"status":"ok","stack":"..."}` |

**Table:** `items (id SERIAL/IDENTITY PK, name TEXT NOT NULL, notes TEXT NULL)`

**Apps (local ports):**

| Stack | Port | DB | Serve mode |
|-------|------|-----|------------|
| Phzyx Forge + FastAPI | 9201 | `bench_phzyx` | **Async** — Uvicorn · **N workers** (asyncio per process) |
| SQLAlchemy 2 + FastAPI | 9202 | `bench_sa` | **Async** — Uvicorn · **N workers** |
| Django | 9203 | `bench_django` | **Sync WSGI** — Gunicorn `gthread` · **N workers × T threads** |

**DSN base:** `postgresql://phzyx:phzyx@127.0.0.1:5518/`

**Fairness knobs:**

- **Matched process count** `N = BENCH_WORKERS` (default 2–4 from CPU) for **all** stacks.
  Async is not stuck on 1 worker while Django scales out.
- Inside each process: async uses the event loop; Django uses `BENCH_THREADS` (default 4) — the sync-native way to parallelize I/O.
- Django is **not** single-worker ASGI (unrealistic for most Django deploys).
- Same JSON contract and table schema; warmup then measured runs.

Env:

```bash
export BENCH_WORKERS=4          # processes for every stack
export BENCH_THREADS=4          # Django gthread threads per worker only
# legacy aliases still work:
# BENCH_DJANGO_WORKERS / BENCH_DJANGO_THREADS
```
