#!/usr/bin/env python3
"""Bulk-seed huge items tables for realistic stack press (all three DBs)."""

from __future__ import annotations

import argparse
import io
import time

import psycopg

CATEGORIES = ("general", "billing", "auth", "media", "ops", "search", "admin", "api")
DBS = ("bench_phzyx", "bench_sa", "bench_django")


def ensure_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            notes TEXT,
            category VARCHAR(64) NOT NULL DEFAULT 'general',
            score INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    # Add columns if old schema
    conn.execute(
        "ALTER TABLE items ADD COLUMN IF NOT EXISTS category VARCHAR(64) DEFAULT 'general'"
    )
    conn.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS score INTEGER DEFAULT 0")
    conn.execute("CREATE INDEX IF NOT EXISTS items_name_idx ON items (name)")
    conn.execute("CREATE INDEX IF NOT EXISTS items_category_idx ON items (category)")
    conn.execute("CREATE INDEX IF NOT EXISTS items_score_idx ON items (score)")
    conn.commit()


def seed_db(name: str, rows: int, host: str, port: int) -> None:
    dsn = f"postgresql://phzyx:phzyx@{host}:{port}/{name}"
    print(f"seeding {name} with {rows:,} rows ...")
    t0 = time.perf_counter()
    with psycopg.connect(dsn) as conn:
        ensure_table(conn)
        conn.execute("TRUNCATE items RESTART IDENTITY")
        conn.commit()
        # COPY in chunks
        chunk = 50_000
        done = 0
        while done < rows:
            n = min(chunk, rows - done)
            buf = io.StringIO()
            for i in range(done, done + n):
                cat = CATEGORIES[i % len(CATEGORIES)]
                score = i % 1000
                # tab-separated for COPY
                item_name = f"item-{i:08d}"
                notes = f"note for {i}"
                buf.write(f"{item_name}\t{notes}\t{cat}\t{score}\n")
            buf.seek(0)
            with (
                conn.cursor() as cur,
                cur.copy("COPY items (name, notes, category, score) FROM STDIN") as copy,
            ):
                copy.write(buf.read())
            conn.commit()
            done += n
            print(f"  {name}: {done:,}/{rows:,}")
        cnt = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    print(f"  done {name}: {cnt:,} rows in {time.perf_counter() - t0:.1f}s")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=250_000)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=5518)
    args = p.parse_args()
    for db in DBS:
        seed_db(db, args.rows, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
