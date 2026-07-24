"""AdminBoard product branding (Django-style white-label)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class BrandingConfig:
    """User-visible product name and Phzyx credit."""

    site_title: str = "AdminBoard"
    header_title: str = "AdminBoard"
    header_subtitle: str = "Phzyx"
    show_powered_by: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> BrandingConfig:
        if not data:
            return cls()
        return cls(
            site_title=str(data.get("site_title") or "AdminBoard"),
            header_title=str(data.get("header_title") or "AdminBoard"),
            header_subtitle=str(data.get("header_subtitle") or "Phzyx"),
            show_powered_by=bool(data.get("show_powered_by", True)),
        )
