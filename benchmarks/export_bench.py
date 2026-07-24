#!/usr/bin/env python3
"""Reproducible list/export micro-benchmark (pure Python path).

Usage (from monorepo root)::

    uv run python benchmarks/export_bench.py --rows 20000

Records wall time for keyset stream CSV export. Does not require Rust.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from phzyx.admin import AdminService, infer_resource, stream_csv
from phzyx.engine import connect, push_schema
from phzyx.orm import Field, Model, Session, bulk_insert
from phzyx.schema.types import Dialect


class BenchRow(Model):
    id: int = Field(primary_key=True)
    name: str = Field()
    value: int = Field(default=0)

    class Meta:
        table = "bench_rows"
        register = False


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=10_000)
    parser.add_argument("--chunk", type=int, default=500)
    args = parser.parse_args()

    db = Path(__file__).with_name("_bench.db")
    if db.exists():
        db.unlink()
    url = f"sqlite:///{db}"
    conn, adapter = connect(url)
    push_schema([BenchRow], conn, adapter, yes=True)
    session = Session(conn, dialect=Dialect.SQLITE)
    t0 = time.perf_counter()
    bulk_insert(
        session,
        BenchRow,
        ({"id": i, "name": f"r{i}", "value": i % 97} for i in range(1, args.rows + 1)),
        chunk_size=args.chunk,
    )
    session.commit()
    insert_s = time.perf_counter() - t0

    res = infer_resource(BenchRow)
    svc = AdminService(resources={"bench_rows": res}, session=session)
    t1 = time.perf_counter()
    n = 0
    for _chunk in stream_csv(res, svc.iter_records("bench_rows", chunk_size=args.chunk)):
        n += 1
    export_s = time.perf_counter() - t1
    session.close()
    conn.close()

    print(f"rows={args.rows}")
    print(f"insert_seconds={insert_s:.4f}")
    print(f"csv_stream_chunks={n}")
    print(f"csv_stream_seconds={export_s:.4f}")
    print("path=pure_python")
    print("rust_core=skip (benches pass pure Python gate; see RESULTS.md)")


if __name__ == "__main__":
    main()
