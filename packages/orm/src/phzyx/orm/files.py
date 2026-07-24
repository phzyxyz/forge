"""File/Image field helpers — keys in DB, not bytes."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import PurePosixPath
from typing import Any

from phzyx.schema.field import Field

_SAFE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def FileField(**kwargs: Any) -> Any:  # noqa: N802
    """Declare a file key column (string path/key in object storage)."""
    kwargs.setdefault("file_kind", "file")
    return Field(**kwargs)


def ImageField(**kwargs: Any) -> Any:  # noqa: N802
    """Declare an image key column (string path/key in object storage)."""
    kwargs.setdefault("file_kind", "image")
    return Field(**kwargs)


def sanitize_upload_key(key: str, *, allow_slash: bool = True) -> str:
    """Reject path traversal and absolute paths in storage keys.

    Raises
    ------
    ValueError
        If the key is empty, absolute, or contains ``..`` segments.
    """
    if not key or not str(key).strip():
        raise ValueError("upload key must be non-empty")
    text = str(key).strip().replace("\\", "/")
    if text.startswith("/") or text.startswith("~"):
        raise ValueError("upload key must not be absolute")
    parts = PurePosixPath(text).parts
    if ".." in parts or any(p == ".." for p in parts):
        raise ValueError("upload key must not contain '..'")
    if not allow_slash and "/" in text:
        raise ValueError("upload key must not contain '/'")
    for part in parts:
        if part in {"", "."}:
            continue
        if not _SAFE_SEGMENT.match(part):
            raise ValueError(f"unsafe upload key segment: {part!r}")
    return "/".join(p for p in parts if p not in {"", "."})


def build_upload_to(
    template: str,
) -> Callable[..., str]:
    """Return an ``upload_to``-style function from a simple template.

    Template may include ``{name}`` placeholders; the result is sanitized.
    """

    def _upload_to(**kwargs: Any) -> str:
        key = template.format(**kwargs)
        return sanitize_upload_key(key)

    return _upload_to
