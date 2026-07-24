"""AdminBoard theme identifiers and ambient resolution."""

from __future__ import annotations

from typing import Literal

ThemeName = Literal["magical-white", "stellar-dark", "system-ambient"]
ResolvedTheme = Literal["magical-white", "stellar-dark"]

PRIMARY_THEMES: tuple[str, ...] = ("magical-white", "stellar-dark")
DEFAULT_THEME: ThemeName = "stellar-dark"


def normalize_theme(theme: str | None) -> ThemeName:
    if theme in {"magical-white", "stellar-dark", "system-ambient"}:
        return theme  # type: ignore[return-value]
    return DEFAULT_THEME


def resolve_theme(
    theme: str | None,
    *,
    prefers_dark: bool | None = None,
) -> ResolvedTheme:
    """Map theme preference to a primary theme.

    ``system-ambient`` follows OS preference when ``prefers_dark`` is provided
    (from ``prefers-color-scheme`` or server-side detection).
    """
    t = normalize_theme(theme)
    if t == "system-ambient":
        if prefers_dark is None:
            return "stellar-dark"  # safe server default
        return "stellar-dark" if prefers_dark else "magical-white"
    return t  # type: ignore[return-value]


def theme_tokens_css(theme: ResolvedTheme, *, reduced_transparency: bool = False) -> str:
    """CSS custom properties snippet for embedding / documentation."""
    if theme == "magical-white":
        bg, text, border = "#f2f2f7", "#1c1c1e", "rgba(0,0,0,0.08)"
        window = "#ffffff" if reduced_transparency else "rgba(255,255,255,0.92)"
    else:
        bg, text, border = "#0b0d12", "rgba(255,255,255,0.92)", "rgba(255,255,255,0.1)"
        window = "#1c1c20" if reduced_transparency else "rgba(28,28,32,0.86)"
    blur = "0" if reduced_transparency else "40px"
    return (
        f"--phzyx-bg-app:{bg};--phzyx-text:{text};--phzyx-border:{border};"
        f"--phzyx-bg-window:{window};--phzyx-blur-window:{blur};"
    )
