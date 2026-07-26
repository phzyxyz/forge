"""Build a ForgePlan from detect result + options."""

from __future__ import annotations

import re
from pathlib import Path

from phzyx.cli.scaffold import templates as T
from phzyx.cli.scaffold.detect import DetectResult
from phzyx.cli.scaffold.presets import normalize_layout, resolve_features
from phzyx.cli.scaffold.types import (
    FileMode,
    FileOp,
    ForgePlan,
    ScaffoldMode,
    ScaffoldOptions,
)

_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")


def validate_name(name: str) -> str:
    name = name.strip()
    if not name or not _NAME_RE.match(name):
        raise ValueError(
            f"invalid project name {name!r}: use letters, digits, _ or - (must start with a letter)"
        )
    if name in {".", ".."}:
        raise ValueError(f"invalid project name {name!r}")
    return name


def _op(rel: str, content: str, *, mode: FileMode = FileMode.CREATE) -> FileOp:
    return FileOp(rel_path=rel, content=content, mode=mode, owned=True)


def build_plan(detect: DetectResult, options: ScaffoldOptions) -> ForgePlan:
    name = validate_name(options.name)
    layout, layout_warning = normalize_layout(options.layout)
    feats = resolve_features(
        options.preset,
        auth=options.auth,
        admin=options.admin,
        docker=options.docker,
    )
    auth = feats["auth"]
    admin = feats["admin"]
    docker = feats["docker"]
    use_meta = feats["use_forge_meta"]

    # Security lock: admin without auth is allowed but warned.
    warnings = list(detect.warnings)
    if admin and not auth:
        warnings.append("Admin without auth uses AllowAll — dev only (see SECURITY.md)")
    if layout_warning:
        warnings.append(layout_warning)

    mode = detect.mode
    root = detect.root
    mr = options.module_root  # "app"

    ops: list[FileOp] = []
    fresh = mode is ScaffoldMode.FRESH

    def add(rel: str, content: str, *, skip_if_exists: bool = False) -> None:
        m = FileMode.SKIP_IF_EXISTS if skip_if_exists else FileMode.CREATE
        if options.force and not skip_if_exists:
            m = FileMode.OVERWRITE
        ops.append(_op(rel, content, mode=m))

    # --- root docs / config ---
    skip_py = options.skip_pyproject or (detect.has_pyproject and not fresh)
    if not skip_py:
        add(
            "pyproject.toml",
            T.pyproject(
                name,
                auth=auth,
                admin=admin,
                use_forge_meta=use_meta or admin,
                db=options.db,
            ),
            skip_if_exists=detect.has_pyproject and not options.force and not fresh,
        )

    if fresh or not (root / "README.md").exists() or options.force:
        add(
            "README.md",
            T.readme(name, auth=auth, admin=admin, preset=options.preset),
            skip_if_exists=not fresh and not options.force,
        )
    add(
        ".gitignore",
        T.gitignore(),
        skip_if_exists=(root / ".gitignore").exists() and not options.force,
    )
    add(
        ".env.example",
        T.env_example(auth=auth, db=options.db),
        skip_if_exists=(root / ".env.example").exists() and not options.force,
    )
    add(
        "SECURITY.md",
        T.security_md(auth=auth, admin=admin),
        skip_if_exists=(root / "SECURITY.md").exists() and not options.force,
    )
    if docker:
        add(
            "docker-compose.yml",
            T.docker_compose(),
            skip_if_exists=(root / "docker-compose.yml").exists() and not options.force,
        )

    # --- app package ---
    add(f"{mr}/__init__.py", T.app_init(), skip_if_exists=True)
    add(f"{mr}/core/__init__.py", T.core_init(), skip_if_exists=True)
    add(
        f"{mr}/core/config.py", T.core_config(), skip_if_exists=not options.force and detect.has_app
    )

    # forge island (always for our modes except we still write on already-init only with force)
    forge = f"{mr}/forge"
    add(f"{forge}/__init__.py", T.forge_init(auth=auth, admin=admin))
    add(f"{forge}/.phzyx-forge", T.forge_marker())
    add(f"{forge}/db.py", T.forge_db())
    add(f"{forge}/models.py", T.forge_models())
    add(f"{forge}/registry.py", T.forge_registry(auth=auth))
    if admin:
        add(f"{forge}/admin.py", T.forge_admin(auth=auth))
        add("ADMIN.md", T.admin_md(), skip_if_exists=True)
    if auth:
        add(f"{forge}/auth.py", T.forge_auth())
        add("AUTH.md", T.auth_md(), skip_if_exists=True)

    # API sample
    write_api = fresh or not detect.has_api
    if write_api:
        add(f"{mr}/api/__init__.py", T.api_init())
        add(f"{mr}/api/deps.py", T.api_deps())
        add(f"{mr}/api/schemas/__init__.py", T.api_schemas_init())
        add(f"{mr}/api/schemas/items.py", T.api_schemas_items())
        add(f"{mr}/api/routes/__init__.py", T.api_routes_init())
        add(f"{mr}/api/routes/health.py", T.api_routes_health())
        add(f"{mr}/api/routes/items.py", T.api_routes_items())

    # main.py
    main_rel = f"{mr}/main.py"
    main_exists = (root / main_rel).is_file()
    write_main = fresh or not main_exists or options.patch_main or options.force
    if options.skip_main and main_exists and not options.force:
        write_main = False
        warnings.append(
            f"skipped {main_rel} — add: from app.forge import mount_forge; mount_forge(app)"
        )
    if not fresh and main_exists and not options.patch_main and not options.force:
        write_main = False
        warnings.append(
            f"existing {main_rel} left unchanged — call mount_forge(app) manually "
            "or re-run with --patch-main / --force"
        )
    if write_main:
        add(main_rel, T.main_py(title=name, auth=auth, admin=admin))

    # tests
    tests_dir = root / "tests"
    write_tests = fresh or not tests_dir.is_dir()
    if write_tests:
        add("tests/conftest.py", T.test_conftest(), skip_if_exists=True)
        add("tests/test_health.py", T.test_health(), skip_if_exists=True)
        add("tests/test_items_api.py", T.test_items(), skip_if_exists=True)

    post = _post_steps(name, root, auth=auth, admin=admin, fresh=fresh)
    return ForgePlan(
        root=root,
        mode=mode,
        options=options,
        ops=ops,
        post_steps=post,
        warnings=warnings,
        layout_warning=layout_warning,
    )


def _post_steps(
    name: str,
    root: Path,
    *,
    auth: bool,
    admin: bool,
    fresh: bool,
) -> list[str]:
    steps = []
    if fresh:
        steps.append(f"cd {root.name if root.name else name}")
    steps.extend(
        [
            "uv sync",
            "cp .env.example .env   # edit secrets",
        ]
    )
    if auth:
        steps.append(
            "export PHZYX_AUTH_SECRET=\"$(python -c 'import secrets; "
            "print(secrets.token_urlsafe(32))')\""
        )
    steps.extend(
        [
            "uv run phzyx db push --models app.forge.registry:ALL_MODELS --yes",
            "uv run uvicorn app.main:app --reload",
            "# open /api/v1/health  /docs  "
            + ("/admin/  " if admin else "")
            + ("/auth/  " if auth else ""),
            "uv run pytest",
            "phzyx doctor",
        ]
    )
    return steps
