# Consolidated stack press — 250k vs 2M rows

Same mixed load, PostgreSQL 18, 2000 requests, concurrency 40, median of 3 runs,
shared RNG seed, stack order shuffled each run.

**Mix:** GET 40% · deep list 15% · category 15% · score 10% · search 10% · create 5% · update 5%

## Overall (median)

| Stack | Scale | RPS | p50 ms | p95 ms | p99 ms | Wall time* |
|-------|-------|----:|-------:|-------:|-------:|-----------:|
| Phzyx Forge | 250k | **1512** | 23.6 | 36.5 | 43.0 | **1.3 s** |
| Phzyx Forge | 2M | **424** | 5.5 | 542 | 678 | **4.7 s** |
| SQLAlchemy | 250k | 480 | 54.6 | 191 | 232 | 4.2 s |
| SQLAlchemy | 2M | 406 | 14.2 | 522 | 656 | 4.9 s |
| Django | 250k | 267 | 151 | 227 | 285 | 7.5 s |
| Django | 2M | 317 | 56.9 | 506 | 650 | 6.3 s |

\*Wall time ≈ 2000 ÷ RPS (seconds to finish the suite at median throughput).

## Why RPS falls at 2M

Deep list and prefix search dominate wall time at multi-million rows. Hot GET /
filter paths stay cheap on Forge (~3–4 ms). Overall RPS is pulled down by the
slow 25% of the mix holding concurrency slots.

## Forge per-op p50 (ms)

| Op | 250k | 2M |
|----|-----:|---:|
| get | 22.4 | 3.5 |
| list_page | 29.7 | 270 |
| list_cat | 22.9 | 4.2 |
| list_score | 22.7 | 4.2 |
| search | 33.1 | 507 |
| create | 24.8 | 11.5 |
| update | 25.9 | 11.6 |

## Site

- Hub gem + `/performance` — graphs for RPS, latency, wall time
- Data: `sites/web/src/data/bench.compare.json`
- Raw 2M: `benchmarks/stack_press/results/realistic.json`
