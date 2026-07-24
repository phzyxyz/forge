"""Storage backends — keys in DB, bytes in storage."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Protocol, runtime_checkable

from phzyx.orm.files import sanitize_upload_key


@runtime_checkable
class StorageBackend(Protocol):
    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str: ...

    def open(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def url(self, key: str) -> str | None:
        """Public or signed URL if available."""
        ...

    def list_keys(self, prefix: str = "") -> list[str]:
        """List storage keys under optional prefix (D6 media library)."""
        ...


class LocalStorage:
    """Filesystem storage for local/dev."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = sanitize_upload_key(key)
        path = (self.root / safe).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("path escapes storage root")
        return path

    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return sanitize_upload_key(key)

    def open(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def url(self, key: str) -> str | None:
        return None

    def list_keys(self, prefix: str = "") -> list[str]:
        root = self.root.resolve()
        pref = sanitize_upload_key(prefix).strip("/") if prefix else ""
        out: list[str] = []
        if not root.is_dir():
            return out
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if pref and not (rel == pref or rel.startswith(pref + "/")):
                continue
            out.append(rel)
        return sorted(out)


class MemoryStorage:
    """In-memory storage for tests."""

    def __init__(self) -> None:
        self._data: dict[str, bytes] = {}

    def save(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        k = sanitize_upload_key(key)
        self._data[k] = data
        return k

    def open(self, key: str) -> bytes:
        k = sanitize_upload_key(key)
        return self._data[k]

    def delete(self, key: str) -> None:
        self._data.pop(sanitize_upload_key(key), None)

    def exists(self, key: str) -> bool:
        return sanitize_upload_key(key) in self._data

    def url(self, key: str) -> str | None:
        return None

    def list_keys(self, prefix: str = "") -> list[str]:
        pref = sanitize_upload_key(prefix).strip("/") if prefix else ""
        keys = sorted(self._data.keys())
        if not pref:
            return keys
        return [k for k in keys if k == pref or k.startswith(pref + "/")]


def guess_content_type(key: str) -> str:
    ctype, _ = mimetypes.guess_type(key)
    return ctype or "application/octet-stream"
