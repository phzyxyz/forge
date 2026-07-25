#!/usr/bin/env bash
# Start Phzyx DB matrix containers (on-demand). Args = families or service names.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if [[ $# -eq 0 ]]; then
  set -- all
fi

services=()
while IFS= read -r line; do
  [[ -n "$line" ]] && services+=("$line")
done < <(services_for_families "$@")

echo "Starting phzyx-dbs: ${services[*]}"
compose up -d "${services[@]}"
wait_healthy "${services[@]}"

# SQL Server images boot into master only — create app DB for tests.
mssql_svcs=()
for s in "${services[@]}"; do
  case "$s" in mssql-*) mssql_svcs+=("$s") ;; esac
done
if [[ ${#mssql_svcs[@]} -gt 0 ]]; then
  mssql_ensure_databases "${mssql_svcs[@]}"
fi

compose ps
echo
echo "DSNs: see docker/dbs/README.md"
echo "Stop when done: ./scripts/dbs/down.sh"
