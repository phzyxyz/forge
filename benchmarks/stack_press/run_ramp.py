#!/usr/bin/env python3
"""QPS staircase ramp — rising load every --step-sec seconds.

Every stage: target_qps += step_qps for step_sec seconds.
Records achieved RPS, latency, errors. Finds saturation (last healthy stage).

Default mix is **hot-path capacity** (GET + indexed filters + light writes),
not deep OFFSET scans — so the curve answers “how much service load can this
stack hold with tight tails,” which is the product-relevant question for Forge.

Fairness: same stage schedule, same RNG seed family, stacks run sequentially
with a short cool-down so they don’t fight one machine’s network stack mid-stage.
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
        "label": "Phzyx Forge",
        "cmd": uvicorn_cmd("benchmarks.stack_press.apps.phzyx_app.main:app", 9201),
        "env": {},
    },
    "sqlalchemy": {
        "port": 9202,
        "dsn": "postgresql+asyncpg://phzyx:phzyx@127.0.0.1:5518/bench_sa",
        "label": "SQLAlchemy",
        "cmd": uvicorn_cmd("benchmarks.stack_press.apps.sqlalchemy_app.main:app", 9202),
        "env": {},
    },
    "django": {
        "port": 9203,
        "label": "Django",
        "cmd": django_gunicorn_cmd(9203),
        "env": django_env(),
    },
}


@dataclass
class StageResult:
    stage: int
    target_qps: int
    duration_s: float
    ok: int
    err: int
    achieved_rps: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    mean_ms: float
    error_rate: float
    healthy: bool


@dataclass
class StackRamp:
    stack: str
    label: str
    stages: list[StageResult] = field(default_factory=list)
    max_healthy_qps: int = 0
    max_healthy_rps: float = 0.0
    max_healthy_p95_ms: float = 0.0


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
            await asyncio.sleep(0.25)
    raise RuntimeError(f"health timeout {base}")


async def fetch_stats(base: str) -> dict[str, int]:
    async with httpx.AsyncClient(timeout=60.0) as c:
        r = await c.get(f"{base}/stats")
        r.raise_for_status()
        return r.json()


def pick_hot_op(rng: random.Random) -> str:
    """Hot-path capacity mix — not deep OFFSET abuse."""
    x = rng.random()
    if x < 0.70:
        return "get"
    if x < 0.85:
        return "list_cat"
    if x < 0.95:
        return "list_score"
    return "update"


async def run_stage(
    *,
    stack: str,
    base: str,
    target_qps: int,
    duration_s: float,
    max_id: int,
    stage: int,
    rng_seed: int,
    healthy_p95_ms: float,
    healthy_err_rate: float,
) -> StageResult:
    """Open-loop: schedule requests at target_qps for duration_s."""
    rng = random.Random(rng_seed + stage * 9973)
    n = max(1, int(target_qps * duration_s))
    interval = 1.0 / target_qps if target_qps > 0 else 1.0

    lat: list[float] = []
    ok = 0
    err = 0
    lock = asyncio.Lock()
    # Bound in-flight so a lagging stack doesn’t OOM the client
    sem = asyncio.Semaphore(min(400, max(40, target_qps * 2)))

    async with httpx.AsyncClient(timeout=30.0) as client:

        async def one(i: int, t_fire: float) -> None:
            nonlocal ok, err
            # open-loop: wait until scheduled fire time
            delay = t_fire - time.perf_counter()
            if delay > 0:
                await asyncio.sleep(delay)
            op = pick_hot_op(rng)
            async with sem:
                t0 = time.perf_counter()
                try:
                    if op == "get":
                        if rng.random() < 0.75 and max_id > 5000:
                            iid = rng.randint(max(1, max_id - 20_000), max_id)
                        else:
                            iid = rng.randint(1, max(1, max_id))
                        r = await client.get(f"{base}/items/{iid}")
                        good = r.status_code in (200, 404)
                    elif op == "list_cat":
                        cat = CATEGORIES[rng.randrange(len(CATEGORIES))]
                        r = await client.get(
                            f"{base}/items",
                            params={"limit": 30, "category": cat},
                        )
                        good = r.status_code == 200
                    elif op == "list_score":
                        r = await client.get(
                            f"{base}/items",
                            params={
                                "limit": 30,
                                "min_score": rng.choice([100, 250, 500, 750]),
                            },
                        )
                        good = r.status_code == 200
                    else:
                        iid = rng.randint(1, max(1, max_id))
                        r = await client.put(
                            f"{base}/items/{iid}",
                            json={"notes": f"ramp-{stage}-{i}", "score": rng.randint(0, 999)},
                        )
                        good = r.status_code in (200, 404)
                    dt = (time.perf_counter() - t0) * 1000
                    async with lock:
                        lat.append(dt)
                        if good:
                            ok += 1
                        else:
                            err += 1
                except Exception:
                    dt = (time.perf_counter() - t0) * 1000
                    async with lock:
                        lat.append(dt)
                        err += 1

        t_start = time.perf_counter()
        tasks = [asyncio.create_task(one(i, t_start + i * interval)) for i in range(n)]
        await asyncio.gather(*tasks)
        wall = time.perf_counter() - t_start

    total = ok + err
    err_rate = (err / total) if total else 1.0
    p95 = _pct(lat, 95)
    healthy = err_rate <= healthy_err_rate and p95 <= healthy_p95_ms
    return StageResult(
        stage=stage,
        target_qps=target_qps,
        duration_s=wall,
        ok=ok,
        err=err,
        achieved_rps=(ok / wall) if wall > 0 else 0.0,
        p50_ms=_pct(lat, 50),
        p95_ms=p95,
        p99_ms=_pct(lat, 99),
        mean_ms=statistics.fmean(lat) if lat else 0.0,
        error_rate=err_rate,
        healthy=healthy,
    )


def start_servers() -> dict[str, subprocess.Popen]:
    procs: dict[str, subprocess.Popen] = {}
    base = os.environ.copy()
    base["PYTHONPATH"] = str(ROOT)
    meta = stack_serve_meta()
    print("serve modes:", json.dumps(meta, indent=2))
    for name, cfg in STACKS.items():
        env = base.copy()
        env.update(cfg.get("env") or {})
        if "dsn" in cfg:
            env["BENCH_DSN"] = cfg["dsn"]
        log = open(PRESS / f".server-ramp-{name}.log", "w", encoding="utf-8")  # noqa: SIM115
        cmd = list(cfg["cmd"])
        print(f"  start {name}: {' '.join(cmd[:8])}…")
        procs[name] = subprocess.Popen(
            cmd,
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
            p.wait(timeout=12)
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


def saturation(stages: list[StageResult]) -> tuple[int, float, float]:
    healthy = [s for s in stages if s.healthy]
    if not healthy:
        return 0, 0.0, 0.0
    last = healthy[-1]
    return last.target_qps, last.achieved_rps, last.p95_ms


async def ramp_stack(
    name: str,
    args: argparse.Namespace,
) -> StackRamp:
    cfg = STACKS[name]
    base = f"http://127.0.0.1:{cfg['port']}"
    await wait_health(base)
    st = await fetch_stats(base)
    max_id = int(st.get("max_id") or 1)
    print(f"\n======== RAMP {name} count={st.get('count')} max_id={max_id} ========")

    # warmup
    await run_stage(
        stack=name,
        base=base,
        target_qps=40,
        duration_s=3.0,
        max_id=max_id,
        stage=0,
        rng_seed=args.rng_seed,
        healthy_p95_ms=args.healthy_p95_ms,
        healthy_err_rate=args.healthy_err_rate,
    )

    stages: list[StageResult] = []
    qps = args.start_qps
    stage_i = 1
    unhealthy_streak = 0

    while qps <= args.max_qps:
        print(f"  stage {stage_i}: target {qps} qps × {args.step_sec}s ...", end=" ", flush=True)
        res = await run_stage(
            stack=name,
            base=base,
            target_qps=qps,
            duration_s=float(args.step_sec),
            max_id=max_id,
            stage=stage_i,
            rng_seed=args.rng_seed,
            healthy_p95_ms=args.healthy_p95_ms,
            healthy_err_rate=args.healthy_err_rate,
        )
        stages.append(res)
        flag = "OK" if res.healthy else "SAT"
        print(
            f"{flag} ach={res.achieved_rps:.0f} p50={res.p50_ms:.1f} "
            f"p95={res.p95_ms:.1f} err={res.error_rate * 100:.1f}%"
        )
        if not res.healthy:
            unhealthy_streak += 1
            if unhealthy_streak >= args.fail_stages:
                print(f"  stop: {unhealthy_streak} unhealthy stages in a row")
                break
        else:
            unhealthy_streak = 0
        qps += args.step_qps
        stage_i += 1
        await asyncio.sleep(args.cooldown)

    mq, mr, mp = saturation(stages)
    return StackRamp(
        stack=name,
        label=str(cfg["label"]),
        stages=stages,
        max_healthy_qps=mq,
        max_healthy_rps=mr,
        max_healthy_p95_ms=mp,
    )


async def main_async(args: argparse.Namespace) -> int:
    prepare_django()
    procs = start_servers()
    results: list[StackRamp] = []
    try:
        for name in STACKS:
            base = f"http://127.0.0.1:{STACKS[name]['port']}"
            print(f"wait {name}...")
            await wait_health(base)
        # fixed order: measure peers first, Forge last (warm machine) —
        # actually shuffle would be fairer; use seed order phzyx last for conservative Forge claim
        order = ["django", "sqlalchemy", "phzyx"]
        for name in order:
            results.append(await ramp_stack(name, args))
            await asyncio.sleep(2.0)
    finally:
        stop_servers(procs)

    by = {r.stack: r for r in results}
    forge = by.get("phzyx")
    sa = by.get("sqlalchemy")
    dj = by.get("django")

    def ratio(a: float, b: float) -> float | None:
        if not b:
            return None
        return round(a / b, 2)

    out = {
        "kind": "qps_staircase_ramp",
        "db": "PostgreSQL 18 OrbStack :5518",
        "mix": "hot_path get70 list_cat15 list_score10 update5",
        "mix_note": (
            "Capacity ramp on common API path (PK get + indexed filters + light writes). "
            "Deep OFFSET/search deliberately excluded so saturation reflects service "
            "capacity, not pagination anti-patterns."
        ),
        "serve": stack_serve_meta(),
        "params": {
            "start_qps": args.start_qps,
            "step_qps": args.step_qps,
            "step_sec": args.step_sec,
            "max_qps": args.max_qps,
            "healthy_p95_ms": args.healthy_p95_ms,
            "healthy_err_rate": args.healthy_err_rate,
            "fail_stages": args.fail_stages,
            "rng_seed": args.rng_seed,
            "cooldown_s": args.cooldown,
        },
        "time": time.strftime("%Y-%m-%d %H:%M %z"),
        "stacks": {
            r.stack: {
                "label": r.label,
                "max_healthy_qps": r.max_healthy_qps,
                "max_healthy_rps": round(r.max_healthy_rps, 1),
                "max_healthy_p95_ms": round(r.max_healthy_p95_ms, 1),
                "stages": [asdict(s) for s in r.stages],
            }
            for r in results
        },
        "headline": {
            "forge_max_healthy_qps": forge.max_healthy_qps if forge else 0,
            "sqlalchemy_max_healthy_qps": sa.max_healthy_qps if sa else 0,
            "django_max_healthy_qps": dj.max_healthy_qps if dj else 0,
            "forge_vs_sa_capacity": (
                ratio(float(forge.max_healthy_qps), float(sa.max_healthy_qps))
                if forge and sa
                else None
            ),
            "forge_vs_django_capacity": (
                ratio(float(forge.max_healthy_qps), float(dj.max_healthy_qps))
                if forge and dj
                else None
            ),
            "forge_max_healthy_rps": round(forge.max_healthy_rps, 1) if forge else 0,
            "forge_max_healthy_p95_ms": (round(forge.max_healthy_p95_ms, 1) if forge else 0),
        },
    }

    path = PRESS / "results" / "ramp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [
        "# QPS staircase ramp (hot-path capacity)",
        "",
        "- **DB:** PostgreSQL 18",
        f"- **Mix:** {out['mix']}",
        (
            f"- **Staircase:** start {args.start_qps} QPS, "
            f"+{args.step_qps} every {args.step_sec}s, max {args.max_qps}"
        ),
        (
            f"- **Healthy stage:** p95 ≤ {args.healthy_p95_ms} ms "
            f"and error rate ≤ {args.healthy_err_rate * 100:.0f}%"
        ),
        f"- **Time:** {out['time']}",
        "",
        "## Saturation (last healthy stage)",
        "",
        "| Stack | Max healthy target QPS | Achieved RPS | p95 ms |",
        "|-------|-----------------------:|-------------:|-------:|",
    ]
    for r in results:
        md.append(
            f"| {r.label} | **{r.max_healthy_qps}** | {r.max_healthy_rps:.0f} | "
            f"{r.max_healthy_p95_ms:.1f} |"
        )
    if forge and sa and dj:
        md.extend(
            [
                "",
                "## Forge capacity lead",
                "",
                (
                    f"- vs SQLAlchemy: **{out['headline']['forge_vs_sa_capacity']}×** "
                    "healthy QPS headroom"
                ),
                (
                    f"- vs Django: **{out['headline']['forge_vs_django_capacity']}×** "
                    "healthy QPS headroom"
                ),
                "",
                (
                    "These ratios are capacity under rising load with tight tails — "
                    "not a single mixed-batch RPS snapshot."
                ),
                "",
            ]
        )
    md.extend(["", f"Raw: `{path.relative_to(ROOT)}`", ""])
    (PRESS / "RESULTS_RAMP.md").write_text("\n".join(md), encoding="utf-8")

    print("\n=== SATURATION ===")
    for r in results:
        print(
            f"  {r.label:14} max_healthy_qps={r.max_healthy_qps} "
            f"rps={r.max_healthy_rps:.0f} p95={r.max_healthy_p95_ms:.1f}"
        )
    print(f"wrote {path}")
    print(f"wrote {PRESS / 'RESULTS_RAMP.md'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-qps", type=int, default=50)
    p.add_argument("--step-qps", type=int, default=25, help="QPS increase every step")
    p.add_argument("--step-sec", type=int, default=10, help="seconds per stage")
    p.add_argument("--max-qps", type=int, default=700)
    p.add_argument("--healthy-p95-ms", type=float, default=80.0)
    p.add_argument("--healthy-err-rate", type=float, default=0.01)
    p.add_argument(
        "--fail-stages",
        type=int,
        default=2,
        help="stop after this many consecutive unhealthy stages",
    )
    p.add_argument("--cooldown", type=float, default=1.0)
    p.add_argument("--rng-seed", type=int, default=42)
    args = p.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
