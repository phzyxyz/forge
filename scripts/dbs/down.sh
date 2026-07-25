#!/usr/bin/env bash
# Stop Phzyx DB matrix containers. --wipe also removes volumes.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

wipe=0
families=()
for arg in "$@"; do
  case "$arg" in
    --wipe|-v|--volumes) wipe=1 ;;
    *) families+=("$arg") ;;
  esac
done

if [[ ${#families[@]} -eq 0 || "${families[0]:-}" == "all" ]]; then
  if [[ "$wipe" -eq 1 ]]; then
    echo "Stopping all phzyx-dbs containers and wiping volumes…"
    compose down -v --remove-orphans
  else
    echo "Stopping all phzyx-dbs containers (volumes kept)…"
    compose stop
  fi
else
  services=()
  while IFS= read -r line; do
    [[ -n "$line" ]] && services+=("$line")
  done < <(services_for_families "${families[@]}")
  echo "Stopping: ${services[*]}"
  compose stop "${services[@]}"
  if [[ "$wipe" -eq 1 ]]; then
    compose rm -f "${services[@]}"
    echo "Note: selective --wipe only removes containers; use down.sh --wipe for volumes."
  fi
fi

compose ps -a 2>/dev/null || true
echo "Done. Start again with: ./scripts/dbs/up.sh"
