#!/usr/bin/env python3
"""Realistic mixed load on a huge items table (Postgres 18).

Traffic mix (default):
  40% GET by random id (hot range + full range)
  15% list page (random offset deep into table)
  15% list by category
  10% list min_score filter
  10% name prefix search
  5% create
  5% update random id

Fairness:
  - Same RNG seed for every stack (identical op/id sequence)
  - Stack order shuffled each run; median across --runs
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import statistics
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
PRESS = Path(__file__).resolve().parent

CATEGORIES = ("general", "billing", "auth", "media", "ops", "search", "admin", "api")

from benchmarks.stack_press.server_cmds import (  # noqa: E402
    django_env,
    django_gunicorn_cmd,
    stack_serve_meta,
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
        # Sync Django as users ship it: WSGI + gunicorn gthread (workers × threads)
        "cmd": django_gunicorn_cmd(9203),
        "env": django_env(),
    },
}


@dataclass
class Result:
    stack: str
    n: int
    concurrency: int
    ok: int
    err: int
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    by_op: dict[str, dict[str, float]]
    run: int = 0
    order_index: int = 0


@dataclass
class MedianResult:
    stack: str
    n: int
    concurrency: int
    runs: int
    rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    ok: int
    err: int
    by_op: dict[str, dict[str, float]] = field(default_factory=dict)
    rps_runs: list[float] = field(default_factory=list)


def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


async def wait_health(base: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as c:
        while time.time() < deadline:
            try:
                r = await c.get(f"{base}/health", timeout=2.0)
                if r.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.3)
    raise RuntimeError(f"health timeout {base}")


async def fetch_stats(base: str) -> dict[str, int]:
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.get(f"{base}/stats")
        r.raise_for_status()
        return r.json()


def pick_op(rng: random.Random) -> str:
    x = rng.random()
    if x < 0.40:
        return "get"
    if x < 0.55:
        return "list_page"
    if x < 0.70:
        return "list_cat"
    if x < 0.80:
        return "list_score"
    if x < 0.90:
        return "search"
    if x < 0.95:
        return "create"
    return "update"


def _plan_requests(
    n: int,
    *,
    max_id: int,
    count: int,
    rng_seed: int,
    stack: str,
) -> list[tuple[str, dict]]:
    """Precompute identical traffic for every stack (no concurrent RNG races)."""
    rng = random.Random(rng_seed)
    plan: list[tuple[str, dict]] = []
    for i in range(n):
        op = pick_op(rng)
        if op == "get":
            if rng.random() < 0.7 and max_id > 1000:
                iid = rng.randint(max(1, max_id - 5000), max_id)
            else:
                iid = rng.randint(1, max(1, max_id))
            plan.append((op, {"iid": iid}))
        elif op == "list_page":
            max_off = max(0, count - 50)
            off = rng.randint(0, max_off) if max_off else 0
            plan.append((op, {"offset": off}))
        elif op == "list_cat":
            plan.append((op, {"category": CATEGORIES[rng.randrange(len(CATEGORIES))]}))
        elif op == "list_score":
            plan.append((op, {"min_score": rng.choice([100, 250, 500, 750, 900])}))
        elif op == "search":
            plan.append((op, {"q": f"item-{rng.randint(0, 9)}"}))
        elif op == "create":
            plan.append(
                (
                    op,
                    {
                        "json": {
                            "name": f"new-{stack}-{i}",
                            "notes": "live",
                            "category": CATEGORIES[i % len(CATEGORIES)],
                            "score": i % 1000,
                        }
                    },
                )
            )
        else:
            plan.append(
                (
                    op,
                    {
                        "iid": rng.randint(1, max(1, max_id)),
                        "json": {
                            "notes": f"upd-{i}",
                            "score": rng.randint(0, 999),
                        },
                    },
                )
            )
    return plan


async def run_mix(
    stack: str,
    base: str,
    *,
    n: int,
    concurrency: int,
    max_id: int,
    count: int,
    rng_seed: int = 42,
    run: int = 0,
    order_index: int = 0,
) -> Result:
    """Identical traffic for every stack when ``rng_seed`` is the same."""
    sem = asyncio.Semaphore(concurrency)
    lat: list[float] = []
    op_lat: dict[str, list[float]] = {}
    ok = 0
    err = 0
    lock = asyncio.Lock()
    plan = _plan_requests(n, max_id=max_id, count=count, rng_seed=rng_seed, stack=stack)

    async with httpx.AsyncClient(timeout=60.0) as client:

        async def one(i: int) -> None:
            nonlocal ok, err
            op, args = plan[i]
            async with sem:
                t0 = time.perf_counter()
                try:
                    if op == "get":
                        r = await client.get(f"{base}/items/{args['iid']}")
                        good = r.status_code in (200, 404)
                    elif op == "list_page":
                        r = await client.get(
                            f"{base}/items",
                            params={"limit": 50, "offset": args["offset"]},
                        )
                        good = r.status_code == 200
                    elif op == "list_cat":
                        r = await client.get(
                            f"{base}/items",
                            params={"limit": 50, "category": args["category"]},
                        )
                        good = r.status_code == 200
                    elif op == "list_score":
                        r = await client.get(
                            f"{base}/items",
                            params={"limit": 50, "min_score": args["min_score"]},
                        )
                        good = r.status_code == 200
                    elif op == "search":
                        r = await client.get(
                            f"{base}/items",
                            params={"limit": 30, "q": args["q"]},
                        )
                        good = r.status_code == 200
                    elif op == "create":
                        r = await client.post(f"{base}/items", json=args["json"])
                        good = r.status_code in (200, 201)
                    else:  # update
                        r = await client.put(
                            f"{base}/items/{args['iid']}",
                            json=args["json"],
                        )
                        good = r.status_code in (200, 404)
                    dt = (time.perf_counter() - t0) * 1000
                    async with lock:
                        lat.append(dt)
                        op_lat.setdefault(op, []).append(dt)
                        if good:
                            ok += 1
                        else:
                            err += 1
                except Exception:
                    dt = (time.perf_counter() - t0) * 1000
                    async with lock:
                        lat.append(dt)
                        op_lat.setdefault(op, []).append(dt)
                        err += 1

        t0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n)))
        wall = time.perf_counter() - t0

    by_op = {
        op: {
            "n": float(len(xs)),
            "p50_ms": _pct(xs, 50),
            "p95_ms": _pct(xs, 95),
            "mean_ms": statistics.fmean(xs) if xs else 0.0,
        }
        for op, xs in op_lat.items()
    }
    return Result(
        stack=stack,
        n=n,
        concurrency=concurrency,
        ok=ok,
        err=err,
        rps=(ok / wall) if wall > 0 else 0.0,
        p50_ms=_pct(lat, 50),
        p95_ms=_pct(lat, 95),
        p99_ms=_pct(lat, 99),
        mean_ms=statistics.fmean(lat) if lat else 0.0,
        by_op=by_op,
        run=run,
        order_index=order_index,
    )


def start_servers() -> dict[str, subprocess.Popen]:
    procs: dict[str, subprocess.Popen] = {}
    base = os.environ.copy()
    base["PYTHONPATH"] = str(ROOT)
    print("serve modes:", json.dumps(stack_serve_meta()))
    for name, cfg in STACKS.items():
        env = base.copy()
        env.update(cfg.get("env") or {})
        if "dsn" in cfg:
            env["BENCH_DSN"] = cfg["dsn"]
        log = open(PRESS / f".server-{name}.log", "w", encoding="utf-8")  # noqa: SIM115
        procs[name] = subprocess.Popen(
            list(cfg["cmd"]),
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
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()


def prepare_django() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["DJANGO_SETTINGS_MODULE"] = "benchmarks.stack_press.apps.django_app.settings"
    env.update(
        {
            "BENCH_DB_NAME": "bench_django",
            "BENCH_DB_HOST": "127.0.0.1",
            "BENCH_DB_PORT": "5518",
            "BENCH_DB_USER": "phzyx",
            "BENCH_DB_PASSWORD": "phzyx",
        }
    )
    subprocess.check_call(
        [sys.executable, "-m", "django", "migrate", "--run-syncdb", "--noinput"],
        cwd=str(ROOT),
        env=env,
    )


def _median_results(all_runs: list[Result]) -> list[MedianResult]:
    by_stack: dict[str, list[Result]] = {}
    for r in all_runs:
        by_stack.setdefault(r.stack, []).append(r)
    out: list[MedianResult] = []
    for stack, runs in by_stack.items():
        # pick the run whose RPS is the median (odd runs recommended)
        ranked = sorted(runs, key=lambda x: x.rps)
        mid = ranked[len(ranked) // 2]
        # median per-op p50 across runs when present
        ops = sorted({op for r in runs for op in r.by_op})
        by_op: dict[str, dict[str, float]] = {}
        for op in ops:
            p50s = [r.by_op[op]["p50_ms"] for r in runs if op in r.by_op]
            p95s = [r.by_op[op]["p95_ms"] for r in runs if op in r.by_op]
            ns = [r.by_op[op]["n"] for r in runs if op in r.by_op]
            by_op[op] = {
                "n": statistics.median(ns) if ns else 0.0,
                "p50_ms": statistics.median(p50s) if p50s else 0.0,
                "p95_ms": statistics.median(p95s) if p95s else 0.0,
                "mean_ms": mid.by_op.get(op, {}).get("mean_ms", 0.0),
            }
        out.append(
            MedianResult(
                stack=stack,
                n=mid.n,
                concurrency=mid.concurrency,
                runs=len(runs),
                rps=statistics.median([r.rps for r in runs]),
                p50_ms=statistics.median([r.p50_ms for r in runs]),
                p95_ms=statistics.median([r.p95_ms for r in runs]),
                p99_ms=statistics.median([r.p99_ms for r in runs]),
                mean_ms=statistics.median([r.mean_ms for r in runs]),
                ok=mid.ok,
                err=mid.err,
                by_op=by_op,
                rps_runs=[r.rps for r in runs],
            )
        )
    # stable display order
    order = {name: i for i, name in enumerate(STACKS)}
    out.sort(key=lambda m: order.get(m.stack, 99))
    return out


async def main_async(args: argparse.Namespace) -> int:
    if args.seed_db:
        subprocess.check_call(
            [
                sys.executable,
                str(PRESS / "seed_huge.py"),
                "--rows",
                str(args.rows),
            ],
            cwd=str(ROOT),
        )

    prepare_django()
    procs = start_servers()
    all_runs: list[Result] = []
    try:
        for name, cfg in STACKS.items():
            base = f"http://127.0.0.1:{cfg['port']}"
            print(f"wait {name}...")
            await wait_health(base)
            st = await fetch_stats(base)
            print(f"  {name}: count={st['count']:,} max_id={st['max_id']}")
            if st["count"] < args.rows // 2:
                print(
                    f"  WARNING: {name} has only {st['count']} rows; "
                    f"re-run with --seed-db --rows {args.rows}"
                )

        # warmup (same seed traffic shape)
        for name, cfg in STACKS.items():
            base = f"http://127.0.0.1:{cfg['port']}"
            st = await fetch_stats(base)
            await run_mix(
                name,
                base,
                n=50,
                concurrency=10,
                max_id=int(st["max_id"] or 1),
                count=int(st["count"] or 1),
                rng_seed=args.rng_seed,
            )

        order_rng = random.Random(args.rng_seed + 7)
        for run_i in range(args.runs):
            names = list(STACKS.keys())
            order_rng.shuffle(names)
            print(f"\n######## run {run_i + 1}/{args.runs} order={names} ########")
            for order_index, name in enumerate(names):
                cfg = STACKS[name]
                base = f"http://127.0.0.1:{cfg['port']}"
                st = await fetch_stats(base)
                print(
                    f"\n=== realistic press {name} "
                    f"(n={args.n} c={args.concurrency} run={run_i + 1}) ==="
                )
                res = await run_mix(
                    name,
                    base,
                    n=args.n,
                    concurrency=args.concurrency,
                    max_id=int(st["max_id"] or 1),
                    count=int(st["count"] or 1),
                    rng_seed=args.rng_seed + run_i * 1000,
                    run=run_i + 1,
                    order_index=order_index,
                )
                all_runs.append(res)
                print(
                    f"  ok={res.ok} err={res.err} rps={res.rps:.1f} "
                    f"p50={res.p50_ms:.1f} p95={res.p95_ms:.1f} p99={res.p99_ms:.1f}"
                )
                for op, m in sorted(res.by_op.items()):
                    print(
                        f"    {op:12} n={int(m['n']):4} p50={m['p50_ms']:.1f}ms "
                        f"p95={m['p95_ms']:.1f}ms"
                    )
    finally:
        stop_servers(procs)

    medians = _median_results(all_runs)
    out = {
        "db": "PostgreSQL 18 OrbStack :5518",
        "rows_target": args.rows,
        "mix": "get40 list_page15 list_cat15 list_score10 search10 create5 update5",
        "fairness": {
            "shared_rng_seed": args.rng_seed,
            "runs": args.runs,
            "stack_order": "shuffled_each_run",
            "identical_op_sequence_per_run": True,
        },
        "phzyx_opts": [
            "session.get PK path",
            "UPDATE RETURNING",
            "asyncpg $n SQL rewrite cache",
            "DTO response build",
        ],
        "all_runs": [asdict(r) for r in all_runs],
        "median": [asdict(m) for m in medians],
    }
    path = PRESS / "results" / "realistic.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [
        "# Realistic huge-DB stack press",
        "",
        "- **DB:** PostgreSQL 18 OrbStack `phzyx-pg-18:5518`",
        f"- **Seed size (target):** {args.rows:,} rows / DB",
        f"- **Requests / concurrency:** {args.n} / {args.concurrency}",
        f"- **Runs (median reported):** {args.runs} (stack order shuffled each run)",
        f"- **RNG:** shared seed `{args.rng_seed}` → identical op mix per stack per run",
        "- **Mix:** get 40%, deep list 15%, by category 15%, min_score 10%, "
        "prefix search 10%, create 5%, update 5%",
        f"- **Time:** {time.strftime('%Y-%m-%d %H:%M %z')}",
        "",
        "## Median overall",
        "",
        "| Stack | Runs | RPS (median) | RPS runs | p50 ms | p95 ms | p99 ms | mean ms |",
        "|-------|-----:|-------------:|----------|-------:|-------:|-------:|--------:|",
    ]
    for m in medians:
        runs_s = ", ".join(f"{x:.0f}" for x in m.rps_runs)
        md.append(
            f"| {m.stack} | {m.runs} | **{m.rps:.1f}** | {runs_s} | {m.p50_ms:.1f} | "
            f"{m.p95_ms:.1f} | {m.p99_ms:.1f} | {m.mean_ms:.1f} |"
        )
    md.extend(["", "## Median per-op p50 (ms)", ""])
    ops = sorted({op for m in medians for op in m.by_op})
    header = "| Stack | " + " | ".join(ops) + " |"
    sep = "|-------|" + "|".join(["-------:"] * len(ops)) + "|"
    md.append(header)
    md.append(sep)
    for m in medians:
        cells = [f"{m.by_op.get(op, {}).get('p50_ms', 0):.1f}" for op in ops]
        md.append(f"| {m.stack} | " + " | ".join(cells) + " |")
    md.extend(
        [
            "",
            "## Notes",
            "",
            "- Deep `offset` scans hurt all stacks (realistic pagination anti-pattern).",
            "- Category / score / prefix filters hit indexed columns.",
            "- Hot GETs bias toward recent IDs (70%) vs uniform (30%).",
            "- Phzyx path: `session.get`, UPDATE RETURNING, `$n` SQL rewrite cache, DTO responses.",
            f"- Raw: `{path.relative_to(ROOT)}`",
            "",
        ]
    )
    out_md = PRESS / "RESULTS_REALISTIC.md"
    out_md.write_text("\n".join(md), encoding="utf-8")
    print(f"\nwrote {out_md}")
    print("\n=== MEDIAN RPS ===")
    for m in medians:
        print(f"  {m.stack:12} {m.rps:.1f}  runs={m.rps_runs}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--rows", type=int, default=250_000, help="seed size if --seed-db")
    p.add_argument(
        "--seed-db",
        action="store_true",
        help="truncate+COPY seed all DBs before press",
    )
    # keep old flag alias
    p.add_argument("--seed", dest="seed_db", action="store_true", help=argparse.SUPPRESS)
    p.add_argument("--n", type=int, default=2000, help="total requests per stack per run")
    p.add_argument("--concurrency", "-c", type=int, default=40)
    p.add_argument("--runs", type=int, default=3, help="full presses; report median RPS")
    p.add_argument("--rng-seed", type=int, default=42, help="shared traffic seed")
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
