"""AdminBoard branding config and settings."""

from __future__ import annotations

from phzyx.admin.branding import BrandingConfig
from phzyx.admin.settings import AdminSettings, SettingsStore


def test_branding_defaults() -> None:
    b = BrandingConfig()
    assert b.site_title == "AdminBoard"
    assert b.header_subtitle == "Phzyx"
    assert b.show_powered_by is True


def test_settings_roundtrip_branding() -> None:
    store = SettingsStore()
    body = store.get().to_dict()
    body["branding"] = {
        "site_title": "Acme Ops",
        "header_title": "Acme Ops",
        "header_subtitle": "Internal",
        "show_powered_by": False,
    }
    out = store.put(AdminSettings.from_dict(body)).to_dict()
    assert out["branding"]["site_title"] == "Acme Ops"
    assert out["branding"]["show_powered_by"] is False


def test_branding_from_dict_partial() -> None:
    b = BrandingConfig.from_dict({"header_title": "Custom"})
    assert b.header_title == "Custom"
    assert b.site_title == "AdminBoard"
