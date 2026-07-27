"""How each stack is served under stack press — **matched process count**.

If Django gets multi-worker, async stacks get the same worker count.

| Stack | Server | Concurrency model |
|-------|--------|-------------------|
| Phzyx / SQLAlchemy | Uvicorn | ``BENCH_WORKERS`` processes × asyncio inside each |
| Django | Gunicorn gthread | ``BENCH_WORKERS`` processes × ``BENCH_THREADS`` threads |

Same process count = same multi-core layout. Inside a process, each stack uses
its natural model (async event loop vs sync threads).
"""

from __future__ import annotations

import os
import sys
from typing import Any


def bench_workers() -> int:
    """Process count shared by all stacks (async Uvicorn + Django Gunicorn)."""
    raw = os.environ.get("BENCH_WORKERS") or os.environ.get("BENCH_DJANGO_WORKERS")
    if raw:
        return max(1, int(raw))
    ncpu = os.cpu_count() or 4
    return max(2, min(4, ncpu))


def bench_threads() -> int:
    """Threads per Django worker only (sync parallelization inside a process)."""
    raw = os.environ.get("BENCH_THREADS") or os.environ.get("BENCH_DJANGO_THREADS")
    if raw:
        return max(1, int(raw))
    return 4


# Back-compat aliases
def django_workers() -> int:
    return bench_workers()


def django_threads() -> int:
    return bench_threads()


def django_gunicorn_cmd(port: int = 9203) -> list[str]:
    """Sync Django: gunicorn WSGI + gthread, same worker count as async stacks."""
    return [
        sys.executable,
        "-m",
        "gunicorn",
        "benchmarks.stack_press.apps.django_app.wsgi:application",
        "--bind",
        f"127.0.0.1:{port}",
        "--worker-class",
        "gthread",
        "--workers",
        str(bench_workers()),
        "--threads",
        str(bench_threads()),
        "--timeout",
        "60",
        "--keep-alive",
        "5",
        "--access-logfile",
        "-",
        "--error-logfile",
        "-",
        "--log-level",
        "warning",
        "--capture-output",
    ]


def django_env() -> dict[str, str]:
    return {
        "DJANGO_SETTINGS_MODULE": "benchmarks.stack_press.apps.django_app.settings",
        "BENCH_DB_NAME": "bench_django",
        "BENCH_DB_HOST": "127.0.0.1",
        "BENCH_DB_PORT": "5518",
        "BENCH_DB_USER": "phzyx",
        "BENCH_DB_PASSWORD": "phzyx",
    }


def uvicorn_cmd(module: str, port: int, workers: int | None = None) -> list[str]:
    """Async FastAPI: Uvicorn multi-process (same ``BENCH_WORKERS`` as Django)."""
    w = bench_workers() if workers is None else max(1, workers)
    return [
        sys.executable,
        "-m",
        "uvicorn",
        module,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--workers",
        str(w),
        "--log-level",
        "warning",
    ]


def stack_serve_meta() -> dict[str, Any]:
    w = bench_workers()
    t = bench_threads()
    return {
        "matched_workers": w,
        "phzyx": {
            "server": "uvicorn",
            "mode": "async",
            "workers": w,
            "note": f"{w} Uvicorn workers; asyncio concurrency per process",
        },
        "sqlalchemy": {
            "server": "uvicorn",
            "mode": "async",
            "workers": w,
            "note": f"{w} Uvicorn workers; asyncio concurrency per process",
        },
        "django": {
            "server": "gunicorn",
            "mode": "sync_wsgi",
            "worker_class": "gthread",
            "workers": w,
            "threads": t,
            "note": f"{w} Gunicorn workers × {t} threads (sync parallelization)",
        },
    }
