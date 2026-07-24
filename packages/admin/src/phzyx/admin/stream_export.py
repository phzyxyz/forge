"""Streaming exports — CSV / JSONL / JSON / Excel with caps and secret exclusion."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from typing import Any

from phzyx.admin.errors import ValidationAdminError
from phzyx.admin.resource import ResourceConfig

# Documented caps (M5 gate).
EXCEL_MAX_ROWS = 100_000
STREAM_DEFAULT_CHUNK = 500
# Soft documentation target: stream without holding full table in RAM.
BOUNDED_RSS_NOTE = (
    "CSV/JSONL streaming iterates keyset chunks; peak RSS stays near chunk size "
    "plus encoder buffers (not the full result set). Excel loads up to EXCEL_MAX_ROWS "
    "in a workbook and is capped."
)


@dataclass
class ExportPolicy:
    max_rows: int | None = None  # None = unlimited for stream formats
    excel_max_rows: int = EXCEL_MAX_ROWS
    chunk_size: int = STREAM_DEFAULT_CHUNK
    audit: Callable[[str, dict[str, Any]], None] | None = None


DEFAULT_EXPORT_POLICY = ExportPolicy()


def _audit(policy: ExportPolicy, event: str, **kwargs: Any) -> None:
    if policy.audit:
        policy.audit(event, kwargs)


def iter_export_rows(
    resource: ResourceConfig,
    row_iter: Iterable[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    max_rows: int | None = None,
) -> Iterator[dict[str, Any]]:
    allowed = set(resource.exportable_columns())
    cols = columns or list(resource.exportable_columns())
    bad = [c for c in cols if c not in allowed]
    if bad:
        raise ValidationAdminError("cannot export excluded columns", columns=bad)
    for n, row in enumerate(row_iter):
        if max_rows is not None and n >= max_rows:
            break
        yield {c: row.get(c) for c in cols}


def stream_csv(
    resource: ResourceConfig,
    row_iter: Iterable[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    policy: ExportPolicy = DEFAULT_EXPORT_POLICY,
) -> Iterator[str]:
    """Yield CSV chunks (header first)."""
    _audit(policy, "export_start", fmt="csv", resource=resource.name)
    cols = columns or list(resource.exportable_columns())
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=cols)
    writer.writeheader()
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)
    for row in iter_export_rows(resource, row_iter, columns=cols, max_rows=policy.max_rows):
        writer.writerow(row)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
    _audit(policy, "export_done", fmt="csv", resource=resource.name)


def stream_jsonl(
    resource: ResourceConfig,
    row_iter: Iterable[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    policy: ExportPolicy = DEFAULT_EXPORT_POLICY,
) -> Iterator[str]:
    _audit(policy, "export_start", fmt="jsonl", resource=resource.name)
    for row in iter_export_rows(resource, row_iter, columns=columns, max_rows=policy.max_rows):
        yield json.dumps(row, default=str) + "\n"
    _audit(policy, "export_done", fmt="jsonl", resource=resource.name)


def stream_json_array(
    resource: ResourceConfig,
    row_iter: Iterable[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    policy: ExportPolicy = DEFAULT_EXPORT_POLICY,
) -> Iterator[str]:
    """Yield a JSON array incrementally without holding all rows."""
    _audit(policy, "export_start", fmt="json", resource=resource.name)
    yield "[\n"
    first = True
    for row in iter_export_rows(resource, row_iter, columns=columns, max_rows=policy.max_rows):
        if not first:
            yield ",\n"
        first = False
        yield json.dumps(row, default=str)
    yield "\n]\n"
    _audit(policy, "export_done", fmt="json", resource=resource.name)


def export_xlsx(
    resource: ResourceConfig,
    row_iter: Iterable[dict[str, Any]],
    *,
    columns: list[str] | None = None,
    policy: ExportPolicy = DEFAULT_EXPORT_POLICY,
) -> bytes:
    """Build an .xlsx workbook (capped). Requires openpyxl."""
    try:
        from openpyxl import Workbook
    except ImportError as exc:  # pragma: no cover
        raise ValidationAdminError("Excel export requires openpyxl: uv add openpyxl") from exc

    cols = columns or list(resource.exportable_columns())
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(resource.name[:31] or "export")
    ws.append(cols)
    n = 0
    for row in iter_export_rows(resource, row_iter, columns=cols, max_rows=policy.excel_max_rows):
        ws.append([row.get(c) for c in cols])
        n += 1
    bio = io.BytesIO()
    wb.save(bio)
    _audit(policy, "export_done", fmt="xlsx", resource=resource.name, rows=n)
    return bio.getvalue()


def materialize_stream(chunks: Iterable[str]) -> str:
    return "".join(chunks)
