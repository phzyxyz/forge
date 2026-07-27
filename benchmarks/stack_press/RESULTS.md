# Stack press results

- **DB:** PostgreSQL **18.4** on OrbStack (`phzyx-pg-18`, host port **5518**)
- **Host:** Mac aarch64, apps on `127.0.0.1`, DB in Docker/OrbStack
- **Workers:** 1 Uvicorn process per stack (fair)
- **N / concurrency:** 200 / 25 (mixed phase uses 100 requests)
- **Generated:** 2026-07-27 03:02 IST

## Summary (RPS, higher is better)

| Phase | Phzyx+FastAPI | SQLAlchemy+FastAPI | Django ASGI |
|-------|--------------:|-------------------:|------------:|
| create | **306.9** | **359.9** | 231.9 |
| get (+create) | **215.9** | 207.4 | 123.2 |
| list | **353.5** | 333.7 | 256.0 |
| update (+create) | 151.6 | **292.3** | 165.3 |
| mixed | **94.8** | 86.8 | 55.0 |

**Takeaways (this run):**

- With an **asyncpg pool**, Phzyx tracks SQLAlchemy on create/get/list/mixed; SQLAlchemy still leads on update.
- Django (sync ORM on ASGI) is solid but slower under concurrent load — expected for this shape.
- First Phzyx pass without a pool was ~3–5× slower; **connection pooling matters** as much as ORM choice.

## Full table

| Stack | Phase | OK | Err | RPS | p50 ms | p95 ms | p99 ms | mean ms |
|-------|-------|---:|----:|----:|-------:|-------:|-------:|--------:|
| phzyx | create | 200 | 0 | 306.9 | 53.7 | 252.7 | 259.3 | 78.0 |
| phzyx | get | 200 | 0 | 215.9 | 90.9 | 242.7 | 306.2 | 109.3 |
| phzyx | list | 200 | 0 | 353.5 | 48.4 | 170.9 | 292.8 | 65.8 |
| phzyx | update | 200 | 0 | 151.6 | 132.1 | 345.3 | 485.1 | 157.7 |
| phzyx | mixed | 100 | 0 | 94.8 | 232.9 | 425.7 | 576.6 | 246.6 |
| sqlalchemy | create | 200 | 0 | 359.9 | 45.9 | 198.2 | 216.6 | 66.2 |
| sqlalchemy | get | 200 | 0 | 207.4 | 78.1 | 253.0 | 264.2 | 117.7 |
| sqlalchemy | list | 200 | 0 | 333.7 | 46.8 | 181.0 | 190.9 | 72.2 |
| sqlalchemy | update | 200 | 0 | 292.3 | 57.4 | 258.4 | 266.6 | 80.4 |
| sqlalchemy | mixed | 100 | 0 | 86.8 | 209.7 | 604.9 | 628.2 | 280.1 |
| django | create | 200 | 0 | 231.9 | 85.3 | 211.9 | 261.5 | 101.4 |
| django | get | 200 | 0 | 123.2 | 159.5 | 422.5 | 548.4 | 191.9 |
| django | list | 200 | 0 | 256.0 | 74.1 | 223.4 | 362.2 | 91.7 |
| django | update | 200 | 0 | 165.3 | 144.9 | 191.1 | 227.0 | 147.9 |
| django | mixed | 100 | 0 | 55.0 | 398.3 | 819.4 | 953.1 | 429.8 |

## Notes

- Same REST contract (`SPEC.md`). Apps under `apps/{phzyx,sqlalchemy,django}_app`.
- Phzyx bench uses **asyncpg pool** + `AsyncSession` (not one new connection per request).
- SQLAlchemy 2.0 async + asyncpg pool.
- Django: **sync ORM** on Uvicorn ASGI (typical).
- End-to-end HTTP + ORM + Postgres, not raw SQL micro-bench.
- Product fix during this work: async Postgres SQL placeholders `%s` → `$n` for asyncpg.

Raw JSON: `benchmarks/stack_press/results/latest.json`

Re-run: `uv run python benchmarks/stack_press/run_press.py --n 200 -c 25`
