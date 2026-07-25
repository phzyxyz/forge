"""Minimal AdminBoard i18n catalog (EN default; extensible)."""

from __future__ import annotations

from typing import Any

# Default English strings for admin chrome / API messages.
DEFAULT_CATALOG: dict[str, str] = {
    "app.title": "AdminBoard",
    "nav.overview": "Overview",
    "nav.resources": "Resources",
    "nav.settings": "Settings",
    "nav.media": "Media",
    "nav.schema": "Schema",
    "nav.audit": "Audit",
    "action.create": "Create",
    "action.save": "Save",
    "action.delete": "Delete",
    "action.export": "Export",
    "action.search": "Search",
    "empty.no_results": "No results",
    "error.not_found": "Not found",
    "error.forbidden": "Forbidden",
    "error.conflict": "Conflict — record was modified elsewhere",
    "error.validation": "Validation failed",
    "error.unique": "already exists",
    "confirm.delete": "Delete this record?",
    "soft_deleted": "Deleted (soft)",
    "include_deleted": "Show deleted",
    "palette.placeholder": "Search records or jump…",
}


class I18n:
    """Simple key → string lookup with optional locale overlay."""

    def __init__(
        self,
        locale: str = "en",
        catalogs: dict[str, dict[str, str]] | None = None,
    ) -> None:
        self.locale = locale
        self._catalogs = {"en": dict(DEFAULT_CATALOG)}
        if catalogs:
            for loc, cat in catalogs.items():
                base = dict(DEFAULT_CATALOG)
                base.update(cat)
                self._catalogs[loc] = base

    def t(self, key: str, **kwargs: Any) -> str:
        cat = self._catalogs.get(self.locale) or self._catalogs["en"]
        text = cat.get(key) or self._catalogs["en"].get(key) or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def catalog(self) -> dict[str, str]:
        return dict(self._catalogs.get(self.locale) or self._catalogs["en"])
