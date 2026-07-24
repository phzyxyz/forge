"""Export CSV/JSON and copy payloads with secret exclusion + size caps."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Sequence
from typing import Any

from phzyx.admin.errors import ValidationAdminError
from phzyx.admin.resource import ResourceConfig

DEFAULT_COPY_MAX_BYTES = 64_000
DEFAULT_EXPORT_MAX_ROWS = 10_000


def rows_for_export(
    resource: ResourceConfig,
    rows: Sequence[dict[str, Any]],
    *,
    columns: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    allowed = set(resource.exportable_columns())
    cols = list(columns) if columns else list(resource.exportable_columns())
    bad = [c for c in cols if c not in allowed]
    if bad:
        raise ValidationAdminError("cannot export excluded columns", columns=bad)
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({c: row.get(c) for c in cols})
    return out


def export_json(
    resource: ResourceConfig,
    rows: Sequence[dict[str, Any]],
    *,
    columns: Sequence[str] | None = None,
    max_rows: int = DEFAULT_EXPORT_MAX_ROWS,
) -> str:
    data = rows_for_export(resource, rows[:max_rows], columns=columns)
    return json.dumps(data, indent=2, default=str)


def export_csv(
    resource: ResourceConfig,
    rows: Sequence[dict[str, Any]],
    *,
    columns: Sequence[str] | None = None,
    max_rows: int = DEFAULT_EXPORT_MAX_ROWS,
) -> str:
    data = rows_for_export(resource, rows[:max_rows], columns=columns)
    if not data:
        cols = list(columns) if columns else list(resource.exportable_columns())
        return ",".join(cols) + "\n"
    buf = io.StringIO()
    cols = list(data[0].keys())
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue()


def copy_payload(
    resource: ResourceConfig,
    rows: Sequence[dict[str, Any]],
    *,
    fmt: str = "json",
    max_bytes: int = DEFAULT_COPY_MAX_BYTES,
    columns: Sequence[str] | None = None,
) -> str:
    if fmt == "json":
        text = export_json(resource, rows, columns=columns)
    elif fmt == "csv":
        text = export_csv(resource, rows, columns=columns)
    else:
        raise ValidationAdminError("fmt must be json or csv")
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        raise ValidationAdminError(
            "copy payload exceeds size cap",
            max_bytes=max_bytes,
            size=len(encoded),
        )
    return text
