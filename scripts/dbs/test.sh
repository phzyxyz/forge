#!/usr/bin/env bash
# Run deep multi-DB matrix tests. Optionally start containers first.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

START=0
PYTEST_ARGS=()
FAMILIES=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --start|--up)
      START=1
      shift
      ;;
    --postgres|--pg)
      FAMILIES+=(postgres)
      shift
      ;;
    --mysql)
      FAMILIES+=(mysql)
      shift
      ;;
    --mariadb)
      FAMILIES+=(mariadb)
      shift
      ;;
    --mssql|--sqlserver)
      FAMILIES+=(mssql)
      shift
      ;;
    --)
      shift
      PYTEST_ARGS+=("$@")
      break
      ;;
    *)
      PYTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

if [[ "$START" -eq 1 ]]; then
  if [[ ${#FAMILIES[@]} -eq 0 ]]; then
    "${SCRIPT_DIR}/up.sh" all
  else
    "${SCRIPT_DIR}/up.sh" "${FAMILIES[@]}"
  fi
fi

export PHZYX_DB_MATRIX=1
# Strict: fail if a matrix target is down (default on when containers expected)
export PHZYX_DB_MATRIX_STRICT="${PHZYX_DB_MATRIX_STRICT:-1}"

cd "$ROOT"
echo "Running DB matrix tests…"
uv run pytest -v --tb=short \
  tests/integration/db_matrix \
  -m "db_matrix" \
  "${PYTEST_ARGS[@]+"${PYTEST_ARGS[@]}"}"
