"""OAuth2 / OIDC provider SPI — Authlib-backed when installed.

v0.1 ships Google + GitHub presets. Install ``phzyx-auth[oauth]`` for live
token exchange; unit tests inject mock providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode

# ── Well-known provider endpoints ──────────────────────────────────────────

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USERINFO_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"

PROVIDER_PRESETS: dict[str, dict[str, Any]] = {
    "google": {
        "authorize_url": GOOGLE_AUTHORIZE_URL,
        "token_url": GOOGLE_TOKEN_URL,
        "userinfo_url": GOOGLE_USERINFO_URL,
        "scopes": ["openid", "email", "profile"],
    },
    "github": {
        "authorize_url": GITHUB_AUTHORIZE_URL,
        "token_url": GITHUB_TOKEN_URL,
        "userinfo_url": GITHUB_USERINFO_URL,
        "scopes": ["read:user", "user:email"],
    },
}


class OAuthProvider(Protocol):
    """Minimal OAuth/OIDC provider contract."""

    name: str

    def authorization_url(self, *, state: str, redirect_uri: str) -> str: ...

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        """Return normalized profile: provider_user_id, email, name, raw, granted_scopes."""
        ...


@dataclass
class OAuthProviderConfig:
    """Client credentials for a provider (Google, GitHub, …)."""

    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    userinfo_url: str | None = None
    scopes: list[str] = field(default_factory=list)

    @classmethod
    def from_preset(
        cls,
        name: str,
        *,
        client_id: str,
        client_secret: str,
        scopes: list[str] | None = None,
    ) -> OAuthProviderConfig:
        key = name.strip().lower()
        if key not in PROVIDER_PRESETS:
            raise ValueError(f"Unknown OAuth preset '{name}' — known: {sorted(PROVIDER_PRESETS)}")
        p = PROVIDER_PRESETS[key]
        return cls(
            name=key,
            client_id=client_id,
            client_secret=client_secret,
            authorize_url=p["authorize_url"],
            token_url=p["token_url"],
            userinfo_url=p.get("userinfo_url"),
            scopes=list(scopes if scopes is not None else p["scopes"]),
        )


class OAuthNotConfiguredError(RuntimeError):
    """Raised when OAuth extra or provider is not installed/configured."""


@dataclass
class StaticOAuthProvider:
    """Test / stub provider — no network."""

    name: str
    authorize_base: str = "https://example.test/oauth/authorize"
    scopes: list[str] = field(default_factory=list)
    # exchange_code returns this profile (inject per test)
    profile: dict[str, Any] = field(
        default_factory=lambda: {
            "provider_user_id": "stub-user-1",
            "email": "oauth@example.test",
            "name": "OAuth User",
            "granted_scopes": [],
            "raw": {},
        }
    )

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        q = urlencode(
            {
                "client_id": "static",
                "redirect_uri": redirect_uri,
                "state": state,
                "response_type": "code",
                "scope": " ".join(self.scopes),
            }
        )
        return f"{self.authorize_base}?{q}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        out = dict(self.profile)
        out.setdefault("granted_scopes", list(self.scopes))
        out["code"] = code
        out["redirect_uri"] = redirect_uri
        return out


@dataclass
class AuthlibOAuthProvider:
    """Live OAuth provider using Authlib + httpx (optional deps)."""

    config: OAuthProviderConfig

    @property
    def name(self) -> str:
        return self.config.name

    def authorization_url(self, *, state: str, redirect_uri: str) -> str:
        params: dict[str, str] = {
            "client_id": self.config.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if self.config.scopes:
            params["scope"] = " ".join(self.config.scopes)
        # Google needs access_type / prompt for offline; keep minimal
        if self.config.name == "google":
            params.setdefault("access_type", "online")
            params.setdefault("include_granted_scopes", "true")
        return f"{self.config.authorize_url}?{urlencode(params)}"

    def exchange_code(self, *, code: str, redirect_uri: str) -> dict[str, Any]:
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover
            raise OAuthNotConfiguredError(
                "Install phzyx-auth[oauth] (authlib + httpx) for live OAuth"
            ) from exc

        token_headers = {"Accept": "application/json"}
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
        }
        with httpx.Client(timeout=30.0) as client:
            tok_resp = client.post(self.config.token_url, data=data, headers=token_headers)
            tok_resp.raise_for_status()
            token_payload = tok_resp.json()
            access = token_payload.get("access_token")
            if not access:
                raise OAuthNotConfiguredError("token response missing access_token")

            headers = {
                "Authorization": f"Bearer {access}",
                "Accept": "application/json",
            }
            userinfo_url = self.config.userinfo_url
            if not userinfo_url:
                raise OAuthNotConfiguredError("userinfo_url not configured")
            ui = client.get(userinfo_url, headers=headers)
            ui.raise_for_status()
            profile = ui.json()

            email = profile.get("email")
            # GitHub may hide email — fetch /user/emails
            if not email and self.config.name == "github":
                em = client.get(GITHUB_EMAILS_URL, headers=headers)
                if em.status_code == 200:
                    for row in em.json() or []:
                        if row.get("primary") and row.get("verified"):
                            email = row.get("email")
                            break
                    if not email and em.json():
                        email = (em.json()[0] or {}).get("email")

        provider_user_id = str(
            profile.get("sub") or profile.get("id") or profile.get("node_id") or ""
        )
        if not provider_user_id:
            raise OAuthNotConfiguredError("could not determine provider user id")

        granted = token_payload.get("scope") or " ".join(self.config.scopes)
        if isinstance(granted, str):
            granted_list = [s for s in granted.replace(",", " ").split() if s]
        else:
            granted_list = list(granted)

        return {
            "provider_user_id": provider_user_id,
            "email": (email or "").strip().lower() or None,
            "name": profile.get("name") or profile.get("login"),
            "granted_scopes": granted_list,
            "raw": {
                "token": {k: v for k, v in token_payload.items() if k != "access_token"},
                "user": profile,
            },
        }


def build_provider(config: OAuthProviderConfig) -> OAuthProvider:
    """Factory — requires ``authlib`` optional dependency for live providers.

    Authlib is declared as the integration surface; token/userinfo HTTP uses
    httpx (also in the oauth extra). Presence of authlib gates production wiring.
    """
    try:
        import authlib  # noqa: F401
    except ImportError as exc:
        raise OAuthNotConfiguredError("Install phzyx-auth[oauth] and configure providers") from exc
    return AuthlibOAuthProvider(config=config)


def preset_config(
    name: str,
    *,
    client_id: str,
    client_secret: str,
    scopes: list[str] | None = None,
) -> OAuthProviderConfig:
    """Shorthand for ``OAuthProviderConfig.from_preset``."""
    return OAuthProviderConfig.from_preset(
        name, client_id=client_id, client_secret=client_secret, scopes=scopes
    )
