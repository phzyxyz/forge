#!/usr/bin/env bash
# Show phzyx-dbs container status and probe TCP ports.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

echo "=== docker compose ps (project=$PROJECT) ==="
compose ps -a || true
echo
echo "=== TCP probes (host ports) ==="
probe() {
  local name="$1" host="$2" port="$3"
  if (echo >/dev/tcp/"$host"/"$port") >/dev/null 2>&1; then
    echo "  OK   $name  ${host}:${port}"
  else
    echo "  DOWN $name  ${host}:${port}"
  fi
}
# bash /dev/tcp may be unavailable in pure sh; use python as fallback
python3 - <<'PY'
import socket
targets = [
    ("pg-18", 5518), ("pg-17", 5517), ("pg-16", 5516), ("pg-15", 5515),
    ("mysql-9", 3609), ("mysql-84", 3608), ("mysql-80", 3600),
    ("mariadb-118", 3718), ("mariadb-114", 3714),
    ("mariadb-1011", 3711), ("mariadb-106", 3706),
    ("mssql-2025", 1425), ("mssql-2022", 1422),
    ("mssql-2019", 1419), ("mssql-2017", 1417),
]
for name, port in targets:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(("127.0.0.1", port))
        print(f"  OK   {name:14} 127.0.0.1:{port}")
    except OSError:
        print(f"  DOWN {name:14} 127.0.0.1:{port}")
    finally:
        s.close()
PY
