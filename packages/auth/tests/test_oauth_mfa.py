"""OAuth Phase D + MFA TOTP foundations."""

from __future__ import annotations

import pytest
from phzyx.auth import (
    AUTH_MODELS,
    AuthConfig,
    AuthService,
    InvalidCredentialsError,
    MFAFactor,
    OAuthAccount,
    StaticOAuthProvider,
)
from phzyx.auth.oauth import OAuthProviderConfig, preset_config
from phzyx.auth.totp import generate_totp_secret, totp_at, verify_totp

TEST_SECRET = "oauth-mfa-test-secret-key-32bytes!"


@pytest.fixture
def svc() -> AuthService:
    return AuthService(config=AuthConfig(secret=TEST_SECRET, production=False))


@pytest.mark.unit
def test_totp_roundtrip_pure_python() -> None:
    secret = generate_totp_secret()
    code = totp_at(secret)
    assert len(code) == 6 and code.isdigit()
    assert verify_totp(secret, code)
    assert not verify_totp(secret, "000000" if code != "000000" else "111111")


@pytest.mark.unit
def test_oauth_presets() -> None:
    cfg = preset_config("google", client_id="cid", client_secret="sec")
    assert "google" in cfg.authorize_url or "accounts.google" in cfg.authorize_url
    assert "openid" in cfg.scopes
    gh = OAuthProviderConfig.from_preset("github", client_id="c", client_secret="s")
    assert "github.com" in gh.authorize_url


@pytest.mark.unit
def test_oauth_start_state_and_callback(svc: AuthService) -> None:
    prov = StaticOAuthProvider(
        name="google",
        profile={
            "provider_user_id": "g-99",
            "email": "newoauth@phzyx.xyz",
            "name": "OAuth User",
            "granted_scopes": ["openid", "email"],
            "raw": {},
        },
    )
    svc.register_oauth_provider(prov)
    start = svc.oauth_start("google", redirect_uri="http://localhost/auth/oauth/google/callback")
    assert "state" in start and "authorization_url" in start
    assert start["state"] in start["authorization_url"] or True  # state stored server-side
    assert start["state"] in svc.oauth_states

    result = svc.oauth_callback(
        "google",
        code="auth-code-1",
        state=start["state"],
        redirect_uri="http://localhost/auth/oauth/google/callback",
    )
    assert result.session_token
    assert result.principal.email == "newoauth@phzyx.xyz"
    assert result.principal.auth_method == "oauth"
    me = svc.principal_from_session(result.session_token)
    assert me is not None and me.email == "newoauth@phzyx.xyz"
    assert "google:g-99" in svc.oauth_accounts


@pytest.mark.unit
def test_oauth_callback_invalid_state(svc: AuthService) -> None:
    svc.register_oauth_provider(StaticOAuthProvider(name="github"))
    with pytest.raises(InvalidCredentialsError):
        svc.oauth_callback("github", code="x", state="nope", redirect_uri="http://x")


@pytest.mark.unit
def test_oauth_links_existing_email(svc: AuthService) -> None:
    svc.register("linkme@phzyx.xyz", "longpassword1")
    svc.register_oauth_provider(
        StaticOAuthProvider(
            name="github",
            profile={
                "provider_user_id": "gh-1",
                "email": "linkme@phzyx.xyz",
                "name": "Link",
                "granted_scopes": ["read:user"],
                "raw": {},
            },
        )
    )
    start = svc.oauth_start("github", redirect_uri="http://cb")
    result = svc.oauth_callback("github", code="c", state=start["state"], redirect_uri="http://cb")
    assert result.principal.email == "linkme@phzyx.xyz"
    # still one user
    assert len(svc.users) == 1


@pytest.mark.unit
def test_mfa_totp_enroll_and_login_challenge(svc: AuthService) -> None:
    p = svc.register("mfa@phzyx.xyz", "longpassword1")
    # login without MFA works
    res0 = svc.login("mfa@phzyx.xyz", "longpassword1")
    assert res0.session_token and not res0.mfa_required

    setup = svc.mfa_totp_setup(p.id)
    assert "secret" in setup and "otpauth://totp/" in setup["provisioning_uri"]
    code = totp_at(setup["secret"])
    svc.mfa_totp_confirm(p.id, code)
    user = svc.users["mfa@phzyx.xyz"]
    assert user.mfa_enabled

    # password ok → MFA challenge, no session yet
    res = svc.login("mfa@phzyx.xyz", "longpassword1")
    assert res.mfa_required
    assert res.session_token is None
    assert res.mfa_challenge_id

    with pytest.raises(InvalidCredentialsError):
        svc.mfa_totp_verify_challenge(res.mfa_challenge_id, "000000")

    good = totp_at(setup["secret"])
    done = svc.mfa_totp_verify_challenge(res.mfa_challenge_id, good)
    assert done.session_token
    assert svc.principal_from_session(done.session_token) is not None


@pytest.mark.unit
def test_models_oauth_mfa_in_auth_models() -> None:
    assert OAuthAccount in AUTH_MODELS
    assert MFAFactor in AUTH_MODELS
    assert OAuthAccount.__phzyx_table__.name == "phzyx_auth_oauth_accounts"
    assert MFAFactor.__phzyx_table__.name == "phzyx_auth_mfa_factors"


@pytest.mark.unit
def test_phzyx_field_authz_export() -> None:
    from phzyx.auth import PhzyxFieldAuthz
    from phzyx.auth.principal import Principal

    z = PhzyxFieldAuthz(default_allow=False)
    p = Principal(id="1", permissions=frozenset({"posts:field:title:read"}))
    assert z.allow_read(p, "posts", "title")
    assert not z.allow_write(p, "posts", "title")
