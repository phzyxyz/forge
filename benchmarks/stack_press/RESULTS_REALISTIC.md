# Realistic huge-DB stack press

- **DB:** PostgreSQL 18 OrbStack `phzyx-pg-18:5518`
- **Seed size (target):** 2,000,000 rows / DB
- **Requests / concurrency:** 2000 / 40
- **Runs (median reported):** 3 (stack order shuffled each run)
- **RNG:** shared seed `42` → identical op mix per stack per run
- **Mix:** get 40%, deep list 15%, by category 15%, min_score 10%, prefix search 10%, create 5%, update 5%
- **Time:** 2026-07-27 17:36 +0530

## Median overall

| Stack | Runs | RPS (median) | RPS runs | p50 ms | p95 ms | p99 ms | mean ms |
|-------|-----:|-------------:|----------|-------:|-------:|-------:|--------:|
| phzyx | 3 | **424.3** | 424, 431, 403 | 5.5 | 542.1 | 678.0 | 91.8 |
| sqlalchemy | 3 | **405.9** | 392, 417, 406 | 14.2 | 522.0 | 655.6 | 95.8 |
| django | 3 | **317.1** | 333, 302, 317 | 56.9 | 505.5 | 650.1 | 123.1 |

## Median per-op p50 (ms)

| Stack | create | get | list_cat | list_page | list_score | search | update |
|-------|-------:|-------:|-------:|-------:|-------:|-------:|-------:|
| phzyx | 11.5 | 3.5 | 4.2 | 270.2 | 4.2 | 507.4 | 11.6 |
| sqlalchemy | 13.3 | 9.9 | 11.0 | 269.9 | 11.6 | 419.4 | 14.6 |
| django | 62.0 | 47.5 | 46.8 | 295.6 | 47.8 | 349.4 | 66.6 |

## Notes

- Deep `offset` scans hurt all stacks (realistic pagination anti-pattern).
- Category / score / prefix filters hit indexed columns.
- Hot GETs bias toward recent IDs (70%) vs uniform (30%).
- Phzyx path: `session.get`, UPDATE RETURNING, `$n` SQL rewrite cache, DTO responses.
- Raw: `benchmarks/stack_press/results/realistic.json`
- Website: hub gem + `/performance` (`sites/web/src/data/bench.*.json`)
