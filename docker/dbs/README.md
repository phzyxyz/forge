# Phzyx local DB matrix (OrbStack)

Multi-version SQL engines for **local battle testing** of schema, engine
(push/migrate), ORM, and Admin. Cloud is out of scope here.

## Matrix

| Engine | Versions (latest → older majors) | Host ports |
|--------|----------------------------------|------------|
| PostgreSQL | 18, 17, 16, 15 | 5518–5515 |
| MySQL | 9, 8.4, 8.0 | 3609, 3608, 3600 |
| MariaDB | 11.8, 11.4, 10.11, 10.6 | 3718, 3714, 3711, 3706 |
| SQL Server | 2025, 2022, 2019, 2017 | 1425, 1422, 1419, 1417 |
| SQLite | host Python sqlite3 | no container |

Credentials (PG/MySQL/MariaDB): user / password / database = `phzyx` / `phzyx` / `phzyx`.  
SQL Server: user `sa` / password `Phzyx_Sql_S3rver!` / database `phzyx` (created by `up.sh`).

Compose project name: **`phzyx-dbs`** (one OrbStack container group).

## Commands

From repo root (OrbStack Docker context recommended):

```bash
./scripts/dbs/up.sh                 # start all + wait healthy
./scripts/dbs/up.sh postgres        # family filter
./scripts/dbs/up.sh mysql mariadb
./scripts/dbs/status.sh
./scripts/dbs/test.sh               # deep matrix suite
./scripts/dbs/test.sh --postgres    # family only
./scripts/dbs/down.sh               # stop containers (keep volumes)
./scripts/dbs/down.sh --wipe        # stop + delete volumes
```

Make / Just:

```bash
make dbs-up
make dbs-test
make dbs-down
```

## DSNs (tests use these)

```text
postgresql://phzyx:phzyx@127.0.0.1:5518/phzyx   # PG 18
postgresql://phzyx:phzyx@127.0.0.1:5517/phzyx   # PG 17
postgresql://phzyx:phzyx@127.0.0.1:5516/phzyx   # PG 16
postgresql://phzyx:phzyx@127.0.0.1:5515/phzyx   # PG 15
mysql://phzyx:phzyx@127.0.0.1:3609/phzyx        # MySQL 9
mysql://phzyx:phzyx@127.0.0.1:3608/phzyx        # MySQL 8.4
mysql://phzyx:phzyx@127.0.0.1:3600/phzyx        # MySQL 8.0
mariadb://phzyx:phzyx@127.0.0.1:3718/phzyx      # MariaDB 11.8
mariadb://phzyx:phzyx@127.0.0.1:3714/phzyx      # MariaDB 11.4
mariadb://phzyx:phzyx@127.0.0.1:3711/phzyx      # MariaDB 10.11
mariadb://phzyx:phzyx@127.0.0.1:3706/phzyx      # MariaDB 10.6
mssql://sa:Phzyx_Sql_S3rver%21@127.0.0.1:1425/phzyx  # SQL Server 2025
mssql://sa:Phzyx_Sql_S3rver%21@127.0.0.1:1422/phzyx  # SQL Server 2022
mssql://sa:Phzyx_Sql_S3rver%21@127.0.0.1:1419/phzyx  # SQL Server 2019
mssql://sa:Phzyx_Sql_S3rver%21@127.0.0.1:1417/phzyx  # SQL Server 2017
```

SQL Server containers use `platform: linux/amd64` on Apple Silicon (OrbStack emulation).  
Driver: `uv add pymssql` (or `phzyx-engine[mssql]` / `phzyx-orm[mssql]`).

## Policy

- Containers **do not** auto-restart (`restart: "no"`). Start only when testing.
- After a matrix run, **`down.sh`** stops them so they are not idle forever.
- Volumes persist data between runs unless `--wipe`.
- Tests skip a target if it is not reachable unless `PHZYX_DB_MATRIX_STRICT=1`.

## Drivers

```bash
uv sync --all-packages --group dev   # includes psycopg, pymysql, asyncpg
```
