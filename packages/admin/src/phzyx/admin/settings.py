"""In-dashboard AdminBoard settings (theme default, export caps, storage)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from phzyx.admin.branding import BrandingConfig
from phzyx.admin.stream_export import EXCEL_MAX_ROWS
from phzyx.admin.themes import DEFAULT_THEME, ThemeName, normalize_theme


@dataclass
class AdminSettings:
    """Mutable settings surface for AdminBoard (persisted by host app)."""

    default_theme: ThemeName = DEFAULT_THEME
    export_max_rows: int | None = None
    excel_max_rows: int = EXCEL_MAX_ROWS
    copy_max_bytes: int = 64_000
    reduced_transparency: bool = False
    allow_public_file_urls: bool = False
    storage_backend: str = "local"  # local | s3 | azure | gcs | memory
    branding: BrandingConfig = field(default_factory=BrandingConfig)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["default_theme"] = normalize_theme(self.default_theme)
        d["branding"] = self.branding.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AdminSettings:
        branding_raw = data.get("branding")
        if isinstance(branding_raw, BrandingConfig):
            branding = branding_raw
        else:
            branding = BrandingConfig.from_dict(
                branding_raw if isinstance(branding_raw, dict) else None
            )
        return cls(
            default_theme=normalize_theme(data.get("default_theme")),
            export_max_rows=data.get("export_max_rows"),
            excel_max_rows=int(data.get("excel_max_rows", EXCEL_MAX_ROWS)),
            copy_max_bytes=int(data.get("copy_max_bytes", 64_000)),
            reduced_transparency=bool(data.get("reduced_transparency", False)),
            allow_public_file_urls=bool(data.get("allow_public_file_urls", False)),
            storage_backend=str(data.get("storage_backend", "local")),
            branding=branding,
            extra=dict(data.get("extra") or {}),
        )


class SettingsStore:
    """Simple in-memory settings store (swap for DB in host apps)."""

    def __init__(self, initial: AdminSettings | None = None) -> None:
        self._settings = initial or AdminSettings()

    def get(self) -> AdminSettings:
        return self._settings

    def put(self, settings: AdminSettings) -> AdminSettings:
        self._settings = settings
        return self._settings

    def patch(self, data: dict[str, Any]) -> AdminSettings:
        merged = {**self._settings.to_dict(), **data}
        self._settings = AdminSettings.from_dict(merged)
        return self._settings
