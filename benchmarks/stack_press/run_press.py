#!/usr/bin/env python3
"""Real stack press: Phzyx vs SQLAlchemy vs Django on Postgres 18.

Starts local apps against OrbStack PG18 (async Uvicorn for Phzyx/SA,
sync Gunicorn WSGI for Django), then hammers identical CRUD endpoints.
Writes RESULTS.md section.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
PRESS = Path(__file__).resolve().parent

from benchmarks.stack_press.server_cmds import (  # noqa: E402
    django_env,
    django_gunicorn_cmd,
    uvicorn_cmd,
)

STACKS = {
    "phzyx": {
        "port": 9201,
        "dsn": "postgresql://phzyx:phzyx@127.0.0.1:5518/bench_phzyx",
        "cmd": uvicorn_cmd("benchmarks.stack_press.apps.phzyx_app.main:app", 9201),
        "env": {},
    },
    "sqlalchemy": {
        "port": 9202,
        "dsn": "postgresql+asyncpg://phzyx:phzyx@127.0.0.1:5518/bench_sa",
        "cmd": uvicorn_cmd("benchmarks.stack_press.apps.sqlalchemy_app.main:app", 9202),
        "env": {},
    },
    "django": {
        "port": 9203,
        "dsn": "postgresql://phzyx:phzyx@127.0.0.1:5518/bench_django",
        # Sync Django as users ship it: WSGI + gunicorn gthread
        "cmd": django_gunicorn_cmd(9203),
        "env": django_env(),
    },
}


@dataclass
class PhaseResult:
    stack: str
    phase: str
    n: int
    concurrency: int
    ok: int
    err: int
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float


def _pct(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    k = min(len(sorted_vals) - 1, max(0, int(round((p / 100.0) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


async def wait_health(base: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            try:
                r = await client.get(f"{base}/health", timeout=2.0)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.25)
    raise RuntimeError(f"health timeout: {base}")


async def truncate_items(base: str) -> None:
    """Best-effort empty table via delete loop + bulk create/delete."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # create one, list, delete all known
        for _ in range(3):
            r = await client.get(f"{base}/items", params={"limit": 200})
            if r.status_code != 200:
                break
            rows = r.json()
            if not rows:
                break
            for row in rows:
                await client.delete(f"{base}/items/{row['id']}")


async def run_phase(
    stack: str,
    base: str,
    phase: str,
    n: int,
    concurrency: int,
) -> PhaseResult:
    sem = asyncio.Semaphore(concurrency)
    latencies: list[float] = []
    ok = 0
    err = 0
    lock = asyncio.Lock()

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def one(i: int) -> None:
            nonlocal ok, err
            async with sem:
                t0 = time.perf_counter()
                try:
                    if phase == "create":
                        r = await client.post(
                            f"{base}/items",
                            json={"name": f"item-{i}", "notes": f"n-{i}"},
                        )
                        good = r.status_code in (200, 201)
                    elif phase == "get":
                        # ensure id exists: create then get
                        c = await client.post(
                            f"{base}/items",
                            json={"name": f"g-{i}", "notes": None},
                        )
                        cid = c.json()["id"]
                        r = await client.get(f"{base}/items/{cid}")
                        good = r.status_code == 200
                    elif phase == "list":
                        r = await client.get(f"{base}/items", params={"limit": 50})
                        good = r.status_code == 200
                    elif phase == "update":
                        c = await client.post(
                            f"{base}/items",
                            json={"name": f"u-{i}", "notes": "a"},
                        )
                        cid = c.json()["id"]
                        r = await client.put(
                            f"{base}/items/{cid}",
                            json={"notes": f"b-{i}"},
                        )
                        good = r.status_code == 200
                    elif phase == "mixed":
                        # realistic mix: create, get, list, update
                        c = await client.post(
                            f"{base}/items",
                            json={"name": f"m-{i}", "notes": "x"},
                        )
                        cid = c.json()["id"]
                        await client.get(f"{base}/items/{cid}")
                        await client.get(f"{base}/items", params={"limit": 20})
                        r = await client.put(
                            f"{base}/items/{cid}",
                            json={"notes": "y"},
                        )
                        good = r.status_code == 200
                    else:
                        raise ValueError(phase)
                    dt = (time.perf_counter() - t0) * 1000.0
                    async with lock:
                        latencies.append(dt)
                        if good:
                            ok += 1
                        else:
                            err += 1
                except Exception:
                    dt = (time.perf_counter() - t0) * 1000.0
                    async with lock:
                        latencies.append(dt)
                        err += 1

        t_wall0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n)))
        wall = time.perf_counter() - t_wall0

    latencies.sort()
    return PhaseResult(
        stack=stack,
        phase=phase,
        n=n,
        concurrency=concurrency,
        ok=ok,
        err=err,
        rps=(ok / wall) if wall > 0 else 0.0,
        p50_ms=_pct(latencies, 50),
        p95_ms=_pct(latencies, 95),
        p99_ms=_pct(latencies, 99),
        mean_ms=statistics.fmean(latencies) if latencies else 0.0,
    )


def start_servers() -> dict[str, subprocess.Popen]:
    procs: dict[str, subprocess.Popen] = {}
    base_env = os.environ.copy()
    base_env["PYTHONPATH"] = str(ROOT)
    for name, cfg in STACKS.items():
        env = base_env.copy()
        env.update(cfg["env"])
        if name == "phzyx" or name == "sqlalchemy":
            env["BENCH_DSN"] = cfg["dsn"]
        log = open(PRESS / f".server-{name}.log", "w", encoding="utf-8")  # noqa: SIM115
        procs[name] = subprocess.Popen(
            cfg["cmd"],
            cwd=str(ROOT),
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    return procs


def stop_servers(procs: dict[str, subprocess.Popen]) -> None:
    for p in procs.values():
        p.terminate()
    for p in procs.values():
        try:
            p.wait(timeout=8)
        except subprocess.TimeoutExpired:
            p.kill()


def prepare_django() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["DJANGO_SETTINGS_MODULE"] = "benchmarks.stack_press.apps.django_app.settings"
    env["BENCH_DB_NAME"] = "bench_django"
    env["BENCH_DB_HOST"] = "127.0.0.1"
    env["BENCH_DB_PORT"] = "5518"
    env["BENCH_DB_USER"] = "phzyx"
    env["BENCH_DB_PASSWORD"] = "phzyx"
    subprocess.check_call(
        [sys.executable, "-m", "django", "migrate", "--run-syncdb", "--noinput"],
        cwd=str(ROOT),
        env=env,
    )


async def async_main(args: argparse.Namespace) -> int:
    prepare_django()
    procs = start_servers()
    results: list[PhaseResult] = []
    try:
        for name, cfg in STACKS.items():
            base = f"http://127.0.0.1:{cfg['port']}"
            print(f"waiting {name} {base} ...")
            await wait_health(base)
            print(f"  healthy: {name}")

        phases = [
            ("create", args.n, args.concurrency),
            ("get", args.n, args.concurrency),
            ("list", args.n, args.concurrency),
            ("update", args.n, args.concurrency),
            ("mixed", max(50, args.n // 2), args.concurrency),
        ]

        for name, cfg in STACKS.items():
            base = f"http://127.0.0.1:{cfg['port']}"
            print(f"\n=== press {name} ===")
            await truncate_items(base)
            # seed some rows for list
            async with httpx.AsyncClient(timeout=30.0) as client:
                for i in range(30):
                    await client.post(
                        f"{base}/items",
                        json={"name": f"seed-{i}", "notes": "s"},
                    )
            # warmup
            await run_phase(name, base, "list", 20, 5)
            for phase, n, conc in phases:
                print(f"  phase={phase} n={n} c={conc}")
                res = await run_phase(name, base, phase, n, conc)
                results.append(res)
                print(
                    f"    ok={res.ok} err={res.err} rps={res.rps:.1f} "
                    f"p50={res.p50_ms:.1f}ms p95={res.p95_ms:.1f}ms p99={res.p99_ms:.1f}ms"
                )
    finally:
        stop_servers(procs)

    out_json = PRESS / "results" / "latest.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "db": "PostgreSQL 18.4 OrbStack phzyx-pg-18 :5518",
        "host": "127.0.0.1",
        "serve": __import__(
            "benchmarks.stack_press.server_cmds", fromlist=["stack_serve_meta"]
        ).stack_serve_meta(),
        "results": [asdict(r) for r in results],
    }
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md_lines = [
        "# Stack press results",
        "",
        "- **DB:** PostgreSQL 18 on OrbStack (`phzyx-pg-18`, port 5518)",
        "- **Workers:** 1 Uvicorn process per stack",
        f"- **N / concurrency:** {args.n} / {args.concurrency} (mixed uses n/2)",
        f"- **Generated:** `{time.strftime('%Y-%m-%d %H:%M:%S %z')}`",
        "",
        "| Stack | Phase | OK | Err | RPS | p50 ms | p95 ms | p99 ms | mean ms |",
        "|-------|-------|---:|----:|----:|-------:|-------:|-------:|--------:|",
    ]
    for r in results:
        md_lines.append(
            f"| {r.stack} | {r.phase} | {r.ok} | {r.err} | {r.rps:.1f} | "
            f"{r.p50_ms:.1f} | {r.p95_ms:.1f} | {r.p99_ms:.1f} | {r.mean_ms:.1f} |"
        )
    md_lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Same REST contract (see `SPEC.md`).",
            "- Phzyx + SQLAlchemy: async sessions over asyncpg.",
            "- Django: typical sync ORM on ASGI (Uvicorn) — common real deployment shape.",
            "- Not a micro-bench of SQL alone; end-to-end HTTP + ORM + Postgres.",
            "",
            f"Raw JSON: `{out_json.relative_to(ROOT)}`",
            "",
        ]
    )
    out_md = PRESS / "RESULTS.md"
    out_md.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"\nwrote {out_md}")
    print(f"wrote {out_json}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Stack press bench")
    p.add_argument("--n", type=int, default=200, help="requests per phase")
    p.add_argument("--concurrency", "-c", type=int, default=20)
    args = p.parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
