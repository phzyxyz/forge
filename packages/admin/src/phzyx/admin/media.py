"""Media library — folder prefixes, storage scan, attach-from-library helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from phzyx.admin.opener import open_meta_for_key
from phzyx.admin.storage import StorageBackend, guess_content_type
from phzyx.orm.files import sanitize_upload_key


@dataclass
class MediaItem:
    key: str
    folder: str
    content_type: str
    size: int | None = None
    mode: str = "download"
    label: str = ""


@dataclass
class MediaLibrary:
    """Catalog over a StorageBackend (prefix = folder)."""

    storage: StorageBackend
    # key -> meta (in-process index; rebuilt from storage.list_keys when empty)
    index: dict[str, MediaItem] = field(default_factory=dict)

    def refresh_from_storage(self, prefix: str = "") -> list[MediaItem]:
        """Scan backend keys into index (D6 library)."""
        list_fn = getattr(self.storage, "list_keys", None)
        keys = list(list_fn(prefix)) if callable(list_fn) else list(self.index.keys())
        for key in keys:
            if key in self.index:
                continue
            ctype = guess_content_type(key)
            meta = open_meta_for_key(key, content_type=ctype)
            folder = key.rsplit("/", 1)[0] if "/" in key else ""
            size = None
            try:
                size = len(self.storage.open(key))
            except Exception:
                size = None
            self.index[key] = MediaItem(
                key=key,
                folder=folder,
                content_type=ctype,
                size=size,
                mode=meta.mode,
                label=meta.label,
            )
        return self.list_folder(prefix)

    def list_folder(self, folder: str = "") -> list[MediaItem]:
        prefix = folder.strip("/")
        out = []
        for item in self.index.values():
            if prefix == "" or item.folder == prefix or item.folder.startswith(prefix + "/"):
                out.append(item)
        return sorted(out, key=lambda i: i.key)

    def add(
        self,
        key: str,
        data: bytes,
        *,
        folder: str = "",
        content_type: str | None = None,
    ) -> MediaItem:
        safe = sanitize_upload_key(key if not folder else f"{folder.strip('/')}/{key}")
        ctype = content_type or guess_content_type(safe)
        saved = self.storage.save(safe, data, content_type=ctype)
        meta = open_meta_for_key(saved, content_type=ctype)
        item = MediaItem(
            key=saved,
            folder=folder.strip("/") or (saved.rsplit("/", 1)[0] if "/" in saved else ""),
            content_type=ctype,
            size=len(data),
            mode=meta.mode,
            label=meta.label,
        )
        self.index[saved] = item
        return item

    def delete(self, key: str) -> None:
        safe = sanitize_upload_key(key)
        self.storage.delete(safe)
        self.index.pop(safe, None)

    def attach_key(self, key: str) -> str:
        """Return a library key for assigning onto a FileField (DB stores key only)."""
        safe = sanitize_upload_key(key)
        if safe not in self.index and not self.storage.exists(safe):
            raise KeyError(f"media key not in library: {safe}")
        return safe

    def to_public(self, item: MediaItem) -> dict:
        return {
            "key": item.key,
            "folder": item.folder,
            "content_type": item.content_type,
            "size": item.size,
            "mode": item.mode,
            "label": item.label or item.key.rsplit("/", 1)[-1],
            "thumb_url": (
                f"/admin/api/v1/files/download?key={item.key}" if item.mode == "image" else None
            ),
        }
