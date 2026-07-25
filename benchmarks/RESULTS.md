# Benchmark results — pure Python path (M5)

## Decision: Rust core

**Skip `phzyx-core` for now.** Pure Python keyset streaming export meets the M5 gate
(bounded-memory CSV/JSONL iteration + Excel caps). Revisit only if production profiles
show encoder-bound hotspots after list/export optimization (plan [17](../research/plan/17_rust_core.md)).

## How to reproduce

```bash
uv sync --all-packages
uv run python benchmarks/export_bench.py --rows 20000
```

## Sample local run (illustrative)

| Metric | Value |
|--------|--------|
| rows | 20000 |
| path | pure Python |
| notes | keyset chunk stream; no full-table list materialization |

Exact timings vary by machine; CI does not enforce absolute thresholds in M5.

## Memory model

- `Session.iter_query` / `AdminService.iter_records` use keyset pages (`chunk_size`).
- CSV/JSONL generators yield incrementally (`phzyx.admin.stream_export`).
- Excel is **capped** at `EXCEL_MAX_ROWS` (100_000) and may hold a write-only workbook buffer.
