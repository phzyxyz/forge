#!/usr/bin/env bash
# Shared helpers for Phzyx local DB matrix scripts.
# Portable: avoid bash-4+ only features (mapfile) for macOS /bin/bash 3.2.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT}/docker/dbs/docker-compose.yml"
PROJECT="phzyx-dbs"

export PATH="/usr/bin:/bin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

compose() {
  docker compose -p "$PROJECT" -f "$COMPOSE_FILE" "$@"
}

# Print service names for families (space-separated on one line via stdout lines).
services_for_families() {
  local f
  local -a out=()
  # bash 3.2: no mapfile; build via echo lines
  for f in "$@"; do
    case "$f" in
      all|"")
        printf '%s\n' pg-18 pg-17 pg-16 pg-15 \
          mysql-9 mysql-84 mysql-80 \
          mariadb-118 mariadb-114 mariadb-1011 mariadb-106 \
          mssql-2025 mssql-2022 mssql-2019 mssql-2017
        ;;
      postgres|pg|postgresql)
        printf '%s\n' pg-18 pg-17 pg-16 pg-15
        ;;
      mysql)
        printf '%s\n' mysql-9 mysql-84 mysql-80
        ;;
      mariadb|maria)
        printf '%s\n' mariadb-118 mariadb-114 mariadb-1011 mariadb-106
        ;;
      mssql|sqlserver|sql-server)
        printf '%s\n' mssql-2025 mssql-2022 mssql-2019 mssql-2017
        ;;
      pg-18|pg-17|pg-16|pg-15|mysql-9|mysql-84|mysql-80|\
      mariadb-118|mariadb-114|mariadb-1011|mariadb-106|\
      mssql-2025|mssql-2022|mssql-2019|mssql-2017)
        printf '%s\n' "$f"
        ;;
      *)
        echo "unknown family/service: $f" >&2
        echo "use: all|postgres|mysql|mariadb|mssql| or a service name" >&2
        return 1
        ;;
    esac
  done | awk 'NF && !seen[$0]++'
}

# Create database `phzyx` on each SQL Server after it is healthy.
mssql_ensure_databases() {
  local svc port
  local pass="Phzyx_Sql_S3rver!"
  local py
  # Prefer workspace venv (has pymssql); fall back to uv run.
  if [[ -x "${ROOT}/.venv/bin/python" ]]; then
    py="${ROOT}/.venv/bin/python"
  else
    py="uv run --directory ${ROOT} python"
  fi
  for svc in "$@"; do
    case "$svc" in
      mssql-2025) port=1425 ;;
      mssql-2022) port=1422 ;;
      mssql-2019) port=1419 ;;
      mssql-2017) port=1417 ;;
      *) continue ;;
    esac
    echo "Ensuring SQL Server database phzyx on ${svc} (:${port})…"
    $py - "$port" "$pass" <<'PY' || true
import sys
import time

port, password = int(sys.argv[1]), sys.argv[2]
try:
    import pymssql
except ImportError:
    print("  pymssql not installed; skip ensure_db (uv add pymssql)", file=sys.stderr)
    sys.exit(0)
last = None
for _attempt in range(40):
    try:
        conn = pymssql.connect(
            server="127.0.0.1",
            port=str(port),
            user="sa",
            password=password,
            database="master",
            login_timeout=5,
            timeout=10,
            autocommit=True,
            tds_version="7.4",
        )
        cur = conn.cursor()
        cur.execute("IF DB_ID(N'phzyx') IS NULL CREATE DATABASE phzyx")
        cur.close()
        conn.close()
        print(f"  OK phzyx ready on :{port}")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        last = exc
        time.sleep(2)
print(f"  WARN could not ensure phzyx on :{port}: {last}", file=sys.stderr)
sys.exit(1)
PY
  done
}

wait_healthy() {
  local timeout="${PHZYX_DB_WAIT_SECS:-240}"
  local start
  start=$(date +%s)
  local services=("$@")
  if [[ ${#services[@]} -eq 0 ]]; then
    local line
    services=()
    while IFS= read -r line; do
      [[ -n "$line" ]] && services+=("$line")
    done < <(services_for_families all)
  fi

  echo "Waiting up to ${timeout}s for healthy: ${services[*]}"
  local pending svc cname st now
  while true; do
    pending=()
    for svc in "${services[@]}"; do
      cname="phzyx-${svc}"
      st="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' \
        "$cname" 2>/dev/null || echo "missing")"
      if [[ "$st" != "healthy" ]]; then
        pending+=("$svc:$st")
      fi
    done
    if [[ ${#pending[@]} -eq 0 ]]; then
      echo "All requested services healthy."
      return 0
    fi
    now=$(date +%s)
    if (( now - start >= timeout )); then
      echo "TIMEOUT waiting for: ${pending[*]}" >&2
      compose ps
      return 1
    fi
    sleep 3
  done
}
