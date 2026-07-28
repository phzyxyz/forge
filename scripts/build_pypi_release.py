#!/usr/bin/env python3
"""Build the public 0.1.0 PyPI surface: fat phzyx-forge + auth + cache only.

Monorepo keeps split packages for development. This script stages a fat
phzyx-forge wheel that vendors schema/engine/orm/admin/cli (+ SPA dist).

Usage (repo root):
  python scripts/build_pypi_release.py
  python scripts/build_pypi_release.py --out dist --skip-smoke

Environment:
  PHZYX_VERSION  override version (default 0.1.0)
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

VERSION = "0.1.0"
PUBLISH_NAMES = ("phzyx-forge", "phzyx-auth", "phzyx-cache")
FORBIDDEN_WHEEL_PREFIXES = (
    "phzyx_schema",
    "phzyx_engine",
    "phzyx_orm",
    "phzyx_admin",
    "phzyx_admin_fastapi",
    "phzyx_admin_litestar",
    "phzyx_cli",
    "phzyx-",  # sdist name phzyx-0.1.0 — meta only; we check carefully below
)

FORGE_README = f"""# phzyx-forge

**Forge** — Phzyx data stack in one install: Pydantic schema, failsafe migrations,
ORM, AdminBoard (FastAPI-first), and the `phzyx` CLI.

```bash
uv add phzyx-forge
```

```python
from phzyx.schema.model import Model
from phzyx.orm import Session
from phzyx.admin.fastapi import AdminBoard
```

Optional batteries (separate packages):

- `phzyx-auth` — identity / sessions / JWT / RBAC (`uv add 'phzyx-forge[auth]'`)
- `phzyx-cache` — versioned resource cache

Pre-1.0: APIs may change. Pin `=={VERSION}` for apps.

Homepage: https://phzyx.xyz · Source: https://github.com/phzyxyz/forge
"""

FORGE_PYPROJECT = f"""\
[project]
name = "phzyx-forge"
version = "{VERSION}"
description = "Phzyx Forge — schema, failsafe migrations, ORM, AdminBoard, CLI"
readme = "README.md"
requires-python = ">=3.11"
license = "MIT"
authors = [{{ name = "Athul Nandaswaroop" }}]
keywords = ["phzyx", "orm", "pydantic", "admin", "migrations", "fastapi"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Programming Language :: Python :: 3.14",
  "Framework :: FastAPI",
  "Topic :: Database",
  "Typing :: Typed",
]
dependencies = [
  "pydantic>=2",
  "fastapi>=0.115",
  "python-multipart>=0.0.32",
  "aiosqlite",  # default local stack; postgres/mysql/mssql stay extras
]

[project.optional-dependencies]
# [sqlite] kept as no-op alias so old docs still resolve
sqlite = []
postgres = ["asyncpg", "psycopg[binary]>=3"]
mysql = ["pymysql"]
mssql = ["pymssql>=2.3"]
auth = ["phzyx-auth[fastapi]>={VERSION},<0.2"]
cache = ["phzyx-cache>={VERSION},<0.2"]
litestar = ["litestar>=2.12"]
full = [
  "phzyx-auth[fastapi]>={VERSION},<0.2",
  "phzyx-cache>={VERSION},<0.2",
]

[project.scripts]
phzyx = "phzyx.cli:main"

[project.urls]
Homepage = "https://phzyx.xyz"
Documentation = "https://phzyx.xyz/docs"
Repository = "https://github.com/phzyxyz/forge"
Issues = "https://github.com/phzyxyz/forge/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/phzyx"]

[tool.hatch.build.targets.sdist]
include = ["src/phzyx", "README.md", "pyproject.toml"]
"""


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def copytree(src: Path, dst: Path) -> None:
    if not src.is_dir():
        raise SystemExit(f"missing source tree: {src}")
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".mypy_cache", ".ruff_cache"),
    )


def stage_fat_forge(root: Path, stage: Path) -> None:
    src_root = stage / "src" / "phzyx"
    src_root.mkdir(parents=True)

    mapping = [
        ("packages/schema/src/phzyx/schema", "schema"),
        ("packages/engine/src/phzyx/engine", "engine"),
        ("packages/orm/src/phzyx/orm", "orm"),
        ("packages/admin/src/phzyx/admin", "admin"),
        ("packages/cli/src/phzyx/cli", "cli"),
    ]
    for rel, name in mapping:
        copytree(root / rel, src_root / name)

    # Adapters merge into admin package
    copytree(
        root / "packages/admin-fastapi/src/phzyx/admin/fastapi",
        src_root / "admin" / "fastapi",
    )
    copytree(
        root / "packages/admin-litestar/src/phzyx/admin/litestar",
        src_root / "admin" / "litestar",
    )

    spa = root / "packages/admin/web/dist"
    if not (spa / "index.html").is_file():
        raise SystemExit(f"AdminBoard SPA missing at {spa}/index.html — run admin web build first")
    copytree(spa, src_root / "admin" / "web" / "dist")

    # Sanity: CLI presets
    presets = list((src_root / "cli" / "presets").glob("*.json"))
    if len(presets) < 3:
        raise SystemExit(f"CLI presets missing in staged tree: {presets}")

    (stage / "README.md").write_text(FORGE_README, encoding="utf-8")
    (stage / "pyproject.toml").write_text(FORGE_PYPROJECT, encoding="utf-8")


def build_fat_forge(root: Path, dist: Path) -> list[Path]:
    dist.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="phzyx-fat-forge-") as tmp:
        stage = Path(tmp)
        stage_fat_forge(root, stage)
        run(["uv", "build", "-o", str(dist.resolve())], cwd=stage)
    # uv/hatch may use underscore in wheel, hyphen in sdist
    found = [
        p
        for p in dist.iterdir()
        if p.name.startswith("phzyx_forge-") or p.name.startswith("phzyx-forge-")
    ]
    if len(found) < 2:
        raise SystemExit(f"expected fat forge wheel+sdist, found: {found}")
    return found


def build_workspace_package(root: Path, name: str, dist: Path) -> None:
    run(["uv", "build", "--package", name, "-o", str(dist.resolve())], cwd=root)


def _dist_artifacts(dist: Path) -> list[Path]:
    """Wheels and sdists only (ignore .gitignore, READMEs, etc.)."""
    out: list[Path] = []
    for p in dist.iterdir():
        if not p.is_file():
            continue
        name = p.name
        if name.endswith(".whl") or name.endswith(".tar.gz"):
            out.append(p)
    return out


def assert_dist_only_public(dist: Path) -> None:
    files = _dist_artifacts(dist)
    if not files:
        raise SystemExit("dist/ has no wheels/sdists")
    # Normalize project names from filenames
    allowed_file_re = re.compile(
        r"^(phzyx_forge|phzyx-forge|phzyx_auth|phzyx-auth|phzyx_cache|phzyx-cache)-"
    )
    bad = [p.name for p in files if not allowed_file_re.match(p.name)]
    if bad:
        raise SystemExit(f"dist/ contains non-public artifacts: {bad}")

    # Explicit forbid list (internal monorepo packages)
    for p in files:
        lower = p.name.lower()
        for prefix in (
            "phzyx_schema",
            "phzyx-schema",
            "phzyx_engine",
            "phzyx-engine",
            "phzyx_orm",
            "phzyx-orm",
            "phzyx_admin",
            "phzyx-admin",
            "phzyx_cli",
            "phzyx-cli",
            "phzyx-0.",  # bare meta phzyx
            "phzyx_0.",
            "phzyx-plugin",
            "phzyx_plugin",
        ):
            if lower.startswith(prefix):
                raise SystemExit(f"forbidden artifact in dist/: {p.name}")

    # Must have all three products (whl + sdist each ideally)
    blob = " ".join(p.name for p in files)
    for token in ("phzyx_forge", "phzyx_auth", "phzyx_cache"):
        # sdist uses hyphens; accept either
        alt = token.replace("_", "-")
        if token not in blob and alt not in blob:
            raise SystemExit(f"missing product in dist/: {token} / {alt}")


def assert_wheel_contents(dist: Path) -> Path:
    wheels = sorted(dist.glob("phzyx_forge-*.whl"))
    if not wheels:
        raise SystemExit("no phzyx_forge wheel")
    wheel = wheels[-1]
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
    need = [
        "phzyx/schema/",
        "phzyx/engine/",
        "phzyx/orm/",
        "phzyx/admin/",
        "phzyx/admin/fastapi/",
        "phzyx/cli/",
        "phzyx/admin/web/dist/index.html",
    ]
    joined = "\n".join(names)
    for n in need:
        if n.endswith("/"):
            has_prefix = any(x.startswith(n) or f"/{n}" in x for x in names)
            has_token = any(n.rstrip("/") in x for x in names)
            if not has_prefix and not has_token:
                raise SystemExit(f"wheel missing {n}: {wheel.name}")
        elif n not in names and not any(x.endswith(n) for x in names):
            raise SystemExit(f"wheel missing {n}\n sample: {names[:20]}")
    if "phzyx/cli/presets/" not in joined and not any("cli/presets" in x for x in names):
        raise SystemExit("wheel missing cli presets")
    print(f"OK wheel contents: {wheel.name} ({len(names)} files)")
    return wheel


def smoke_install(root: Path, dist: Path, wheel: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="phzyx-smoke-") as tmp:
        venv = Path(tmp) / "venv"
        run(["uv", "venv", str(venv)], cwd=root)
        py = venv / "bin" / "python"
        forge_whl = wheel.resolve()
        # Install forge[sqlite] from local wheel; prefer offline path
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(py),
                str(forge_whl),
            ],
            cwd=root,
        )
        run(
            [
                str(py),
                "-c",
                "from phzyx.schema.model import Model; "
                "from phzyx.orm.session_sync import Session; "
                "from phzyx.admin.fastapi import AdminBoard; "
                "from phzyx.admin.fastapi.board import _spa_static_dir; "
                "d=_spa_static_dir(); "
                "assert d is not None and (d/'index.html').is_file(), d; "
                "print('imports+spa_ok', d)",
            ],
            cwd=root,
        )
        run([str(venv / "bin" / "phzyx"), "--help"], cwd=root)

        auth_wheels = sorted(dist.glob("phzyx_auth-*.whl"))
        cache_wheels = sorted(dist.glob("phzyx_cache-*.whl"))
        if not auth_wheels or not cache_wheels:
            raise SystemExit("auth/cache wheels missing for smoke")
        run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(py),
                str(auth_wheels[-1].resolve()),
                str(cache_wheels[-1].resolve()),
            ],
            cwd=root,
        )
        run(
            [
                str(py),
                "-c",
                "import phzyx.auth; import phzyx.cache; print('auth+cache_ok')",
            ],
            cwd=root,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=None, help="dist directory")
    parser.add_argument("--skip-smoke", action="store_true")
    parser.add_argument("--clean", action="store_true", help="wipe dist/ first")
    args = parser.parse_args()
    root = repo_root()
    dist = (args.out or (root / "dist")).resolve()
    if args.clean and dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True, exist_ok=True)

    # Drop prior artifacts so assert is clean
    for p in _dist_artifacts(dist):
        p.unlink()

    print("==> fat phzyx-forge")
    build_fat_forge(root, dist)
    print("==> phzyx-auth")
    build_workspace_package(root, "phzyx-auth", dist)
    print("==> phzyx-cache")
    build_workspace_package(root, "phzyx-cache", dist)

    assert_dist_only_public(dist)
    wheel = assert_wheel_contents(dist)
    print("dist artifacts:")
    for p in sorted(dist.iterdir()):
        print(f"  {p.name}")

    if not args.skip_smoke:
        print("==> clean venv smoke")
        smoke_install(root, dist, wheel)

    print("OK public PyPI surface built:", ", ".join(PUBLISH_NAMES))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as e:
        print(f"command failed: {e}", file=sys.stderr)
        raise SystemExit(e.returncode) from e
