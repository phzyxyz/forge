# QPS staircase ramp (hot-path capacity)

- **DB:** PostgreSQL 18
- **Mix:** hot_path get70 list_cat15 list_score10 update5
- **Staircase:** start 50 QPS, +25 every 10s, up to 1200
- **Healthy stage:** p95 ≤ 80.0 ms and error rate ≤ 1%
- **Time:** 2026-07-27 18:14 +0530

## Saturation (last healthy stage)

| Stack | Max healthy target QPS | Achieved RPS | p95 ms |
|-------|-----------------------:|-------------:|-------:|
| Django | **550** | 550 | 7.0 |
| SQLAlchemy | **775** | 775 | 2.5 |
| Phzyx Forge | **1125** | 1121 | 2.4 |

## Forge capacity lead (primary result)

| | Max healthy QPS | Achieved RPS | p95 at peak |
|--|----------------:|-------------:|------------:|
| **Phzyx Forge** | **1125** | **1121** | **2.4 ms** |
| SQLAlchemy | 775 | 775 | 2.5 ms |
| Django | 550 | 550 | 7.0 ms |

- vs SQLAlchemy: **1.45×** healthy QPS headroom  
- vs Django: **2.05×** healthy QPS headroom  

Forge still holds **sub‑3 ms p95** at the highest healthy stage. Peers leave the healthy band earlier on the same staircase.

**Serve fairness:** 4 processes each for Forge, SQLAlchemy, and Django.

These ratios are **capacity under rising load with tight tails** — the production-shaped story — not a single mixed-batch RPS snapshot flattened by deep OFFSET/search.


Raw: `benchmarks/stack_press/results/ramp.json`
