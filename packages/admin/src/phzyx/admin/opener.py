"""Typed in-dashboard file opener metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from phzyx.admin.storage import guess_content_type

OpenMode = Literal["image", "pdf", "text", "audio", "video", "download"]


@dataclass(frozen=True, slots=True)
class OpenMeta:
    key: str
    content_type: str
    mode: OpenMode
    label: str


def open_meta_for_key(key: str, *, content_type: str | None = None) -> OpenMeta:
    """Pick viewer mode from MIME type; unknown → download."""
    ctype = content_type or guess_content_type(key)
    mode: OpenMode = "download"
    if ctype.startswith("image/"):
        mode = "image"
    elif ctype == "application/pdf":
        mode = "pdf"
    elif ctype.startswith("text/") or ctype in {"application/json", "application/xml"}:
        mode = "text"
    elif ctype.startswith("audio/"):
        mode = "audio"
    elif ctype.startswith("video/"):
        mode = "video"
    return OpenMeta(key=key, content_type=ctype, mode=mode, label=key.rsplit("/", 1)[-1])
