"""Fixtures for the multi-version DB matrix."""

from __future__ import annotations

import os

import pytest

from .targets import NETWORK_TARGETS, DbTarget, require_or_skip, sqlite_target


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip db_matrix tests unless explicitly enabled.

    Keeps default ``uv run pytest`` / CI unit runs fast. Opt in with::

        PHZYX_DB_MATRIX=1 ./scripts/dbs/test.sh
    """
    if os.environ.get("PHZYX_DB_MATRIX", "").lower() in {"1", "true", "yes"}:
        return
    skip = pytest.mark.skip(reason="db_matrix off (set PHZYX_DB_MATRIX=1 and ./scripts/dbs/up.sh)")
    for item in items:
        if "db_matrix" in item.keywords:
            item.add_marker(skip)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Parametrize any test that asks for ``db_target`` across the matrix."""
    if "db_target" not in metafunc.fixturenames:
        return
    # Optional markers to narrow: @pytest.mark.postgres etc. are on modules/tests
    markers = {m.name for m in metafunc.definition.iter_markers()}
    targets: list[DbTarget] = []

    # Always include a fresh sqlite file path id — resolved in fixture via tmp_path
    want_sqlite = "sqlite_only" in markers or not markers.intersection(
        {"postgres_only", "mysql_only", "mariadb_only", "network_only"}
    )
    if "network_only" in markers:
        want_sqlite = False
    if "postgres_only" in markers:
        targets.extend(t for t in NETWORK_TARGETS if t.family == "postgres")
    elif "mysql_only" in markers:
        targets.extend(t for t in NETWORK_TARGETS if t.family == "mysql")
    elif "mariadb_only" in markers:
        targets.extend(t for t in NETWORK_TARGETS if t.family == "mariadb")
    elif "mssql_only" in markers:
        targets.extend(t for t in NETWORK_TARGETS if t.family == "mssql")
    else:
        targets.extend(NETWORK_TARGETS)
        if want_sqlite:
            # placeholder; real path set in fixture
            targets = [sqlite_target("__PATH__"), *targets]

    # Env family filter
    import os

    fam = os.environ.get("PHZYX_DB_MATRIX_FAMILY", "").strip().lower()
    only = os.environ.get("PHZYX_DB_MATRIX_ONLY", "").strip().lower()
    if fam and fam != "all":
        targets = [t for t in targets if t.family == fam or t.id == fam]
    if only:
        targets = [t for t in targets if t.id == only or t.family == only]

    ids = [t.id for t in targets]
    metafunc.parametrize("db_target", targets, ids=ids, indirect=True)


@pytest.fixture()
def db_target(request: pytest.FixtureRequest, tmp_path) -> DbTarget:
    target: DbTarget = request.param
    if target.id == "sqlite":
        path = tmp_path / "matrix.db"
        target = sqlite_target(str(path))
    require_or_skip(target)
    return target
