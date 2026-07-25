"""Matrix targets for local multi-version DB battle tests.

Maps compose services → DSNs used by Phzyx engine/ORM.
SQLite is always available in-process (no container).
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass

from phzyx.schema.types import Dialect

USER = "phzyx"
PASSWORD = "phzyx"
DATABASE = "phzyx"
HOST = "127.0.0.1"

# SQL Server SA password (must meet complexity; URL-encoded in DSN).
MSSQL_USER = "sa"
MSSQL_PASSWORD = "Phzyx_Sql_S3rver!"
MSSQL_PASSWORD_URL = "Phzyx_Sql_S3rver%21"


@dataclass(frozen=True, slots=True)
class DbTarget:
    """One concrete engine version under test."""

    id: str
    family: str  # postgres | mysql | mariadb | sqlite
    version_label: str
    dialect: Dialect
    url: str
    container: str | None  # compose container name, if any
    port: int | None

    @property
    def is_sqlite(self) -> bool:
        return self.dialect is Dialect.SQLITE

    @property
    def is_postgres(self) -> bool:
        return self.dialect is Dialect.POSTGRES

    @property
    def is_mysql_wire(self) -> bool:
        return self.dialect is Dialect.MYSQL


# Fixed host ports match docker/dbs/docker-compose.yml
NETWORK_TARGETS: tuple[DbTarget, ...] = (
    DbTarget(
        id="pg-18",
        family="postgres",
        version_label="18",
        dialect=Dialect.POSTGRES,
        url=f"postgresql://{USER}:{PASSWORD}@{HOST}:5518/{DATABASE}",
        container="phzyx-pg-18",
        port=5518,
    ),
    DbTarget(
        id="pg-17",
        family="postgres",
        version_label="17",
        dialect=Dialect.POSTGRES,
        url=f"postgresql://{USER}:{PASSWORD}@{HOST}:5517/{DATABASE}",
        container="phzyx-pg-17",
        port=5517,
    ),
    DbTarget(
        id="pg-16",
        family="postgres",
        version_label="16",
        dialect=Dialect.POSTGRES,
        url=f"postgresql://{USER}:{PASSWORD}@{HOST}:5516/{DATABASE}",
        container="phzyx-pg-16",
        port=5516,
    ),
    DbTarget(
        id="pg-15",
        family="postgres",
        version_label="15",
        dialect=Dialect.POSTGRES,
        url=f"postgresql://{USER}:{PASSWORD}@{HOST}:5515/{DATABASE}",
        container="phzyx-pg-15",
        port=5515,
    ),
    DbTarget(
        id="mysql-9",
        family="mysql",
        version_label="9",
        dialect=Dialect.MYSQL,
        url=f"mysql://{USER}:{PASSWORD}@{HOST}:3609/{DATABASE}",
        container="phzyx-mysql-9",
        port=3609,
    ),
    DbTarget(
        id="mysql-84",
        family="mysql",
        version_label="8.4",
        dialect=Dialect.MYSQL,
        url=f"mysql://{USER}:{PASSWORD}@{HOST}:3608/{DATABASE}",
        container="phzyx-mysql-84",
        port=3608,
    ),
    DbTarget(
        id="mysql-80",
        family="mysql",
        version_label="8.0",
        dialect=Dialect.MYSQL,
        url=f"mysql://{USER}:{PASSWORD}@{HOST}:3600/{DATABASE}",
        container="phzyx-mysql-80",
        port=3600,
    ),
    DbTarget(
        id="mariadb-118",
        family="mariadb",
        version_label="11.8",
        dialect=Dialect.MYSQL,  # wire-compatible; MariaDB schemes map here
        url=f"mariadb://{USER}:{PASSWORD}@{HOST}:3718/{DATABASE}",
        container="phzyx-mariadb-118",
        port=3718,
    ),
    DbTarget(
        id="mariadb-114",
        family="mariadb",
        version_label="11.4",
        dialect=Dialect.MYSQL,
        url=f"mariadb://{USER}:{PASSWORD}@{HOST}:3714/{DATABASE}",
        container="phzyx-mariadb-114",
        port=3714,
    ),
    DbTarget(
        id="mariadb-1011",
        family="mariadb",
        version_label="10.11",
        dialect=Dialect.MYSQL,
        url=f"mariadb://{USER}:{PASSWORD}@{HOST}:3711/{DATABASE}",
        container="phzyx-mariadb-1011",
        port=3711,
    ),
    DbTarget(
        id="mariadb-106",
        family="mariadb",
        version_label="10.6",
        dialect=Dialect.MYSQL,
        url=f"mariadb://{USER}:{PASSWORD}@{HOST}:3706/{DATABASE}",
        container="phzyx-mariadb-106",
        port=3706,
    ),
    DbTarget(
        id="mssql-2025",
        family="mssql",
        version_label="2025",
        dialect=Dialect.MSSQL,
        url=f"mssql://{MSSQL_USER}:{MSSQL_PASSWORD_URL}@{HOST}:1425/{DATABASE}",
        container="phzyx-mssql-2025",
        port=1425,
    ),
    DbTarget(
        id="mssql-2022",
        family="mssql",
        version_label="2022",
        dialect=Dialect.MSSQL,
        url=f"mssql://{MSSQL_USER}:{MSSQL_PASSWORD_URL}@{HOST}:1422/{DATABASE}",
        container="phzyx-mssql-2022",
        port=1422,
    ),
    DbTarget(
        id="mssql-2019",
        family="mssql",
        version_label="2019",
        dialect=Dialect.MSSQL,
        url=f"mssql://{MSSQL_USER}:{MSSQL_PASSWORD_URL}@{HOST}:1419/{DATABASE}",
        container="phzyx-mssql-2019",
        port=1419,
    ),
    DbTarget(
        id="mssql-2017",
        family="mssql",
        version_label="2017",
        dialect=Dialect.MSSQL,
        url=f"mssql://{MSSQL_USER}:{MSSQL_PASSWORD_URL}@{HOST}:1417/{DATABASE}",
        container="phzyx-mssql-2017",
        port=1417,
    ),
)


def sqlite_target(path: str) -> DbTarget:
    return DbTarget(
        id="sqlite",
        family="sqlite",
        version_label="host",
        dialect=Dialect.SQLITE,
        url=f"sqlite:///{path}",
        container=None,
        port=None,
    )


def port_open(host: str, port: int, timeout: float = 0.35) -> bool:
    sock = socket.socket()
    sock.settimeout(timeout)
    try:
        sock.connect((host, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def target_reachable(target: DbTarget) -> bool:
    if target.is_sqlite:
        return True
    if target.port is None:
        return False
    return port_open(HOST, target.port)


def selected_targets(
    *,
    include_sqlite: bool = True,
    sqlite_path: str | None = None,
) -> list[DbTarget]:
    """Return targets for this pytest run based on env filters."""
    family_filter = os.environ.get("PHZYX_DB_MATRIX_FAMILY", "").strip().lower()
    id_filter = os.environ.get("PHZYX_DB_MATRIX_ONLY", "").strip().lower()
    out: list[DbTarget] = []

    if (
        include_sqlite
        and sqlite_path is not None
        and (not family_filter or family_filter in {"sqlite", "all"})
        and (not id_filter or id_filter == "sqlite")
    ):
        out.append(sqlite_target(sqlite_path))

    for t in NETWORK_TARGETS:
        if family_filter and family_filter not in {"all", t.family, t.id}:
            # allow PHZYX_DB_MATRIX_FAMILY=postgres
            continue
        if id_filter and id_filter not in {t.id, t.family}:
            continue
        out.append(t)
    return out


def require_or_skip(target: DbTarget) -> None:
    """Skip (or fail in strict mode) when a network target is down."""
    import pytest

    if target.is_sqlite:
        return
    if target_reachable(target):
        return
    msg = (
        f"DB target {target.id} not reachable on {HOST}:{target.port}. "
        f"Start with: ./scripts/dbs/up.sh {target.family}"
    )
    matrix_on = os.environ.get("PHZYX_DB_MATRIX", "").lower() in {"1", "true", "yes"}
    strict_raw = os.environ.get("PHZYX_DB_MATRIX_STRICT", "1" if matrix_on else "0")
    strict = strict_raw.lower() in {"1", "true", "yes"}
    if strict:
        pytest.fail(msg)
    pytest.skip(msg)
