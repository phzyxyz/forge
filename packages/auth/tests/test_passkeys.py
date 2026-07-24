"""Passkey / WebAuthn flows (HMAC backend)."""

from __future__ import annotations

import pytest
from phzyx.auth import AuthConfig, AuthService, HmacPasskeyBackend, sign_hmac_assertion
from phzyx.auth.password import PasswordHasher


@pytest.fixture
def svc() -> AuthService:
    return AuthService(
        config=AuthConfig(
            secret="passkey-test-secret-key-32bytes!!",
            production=False,
            password=PasswordHasher(min_length=5),
            webauthn_rp_id="localhost",
            webauthn_origin="http://localhost",
        ),
        passkey_backend=HmacPasskeyBackend(),
    )


@pytest.mark.unit
def test_passkey_register_and_auth(svc: AuthService) -> None:
    p = svc.register("pk@phzyx.xyz", "longpassword1")
    opts = svc.passkey_register_begin(p.id)
    assert "challenge" in opts
    public_key = "dev-secret-key-material-for-hmac"
    cred_id = "cred-abc-001"
    complete = svc.passkey_register_complete(
        p.id,
        {
            "id": cred_id,
            "rawId": cred_id,
            "type": "public-key",
            "response": {
                "clientDataJSON": "",
                "publicKey": public_key,
            },
        },
    )
    assert complete["ok"] is True
    assert complete["mfa_enabled"] is True
    keys = svc.list_passkeys(p.id)
    assert len(keys) == 1

    begin = svc.passkey_auth_begin(email="pk@phzyx.xyz")
    challenge = begin["challenge"]
    sig = sign_hmac_assertion(public_key=public_key, challenge=challenge, credential_id=cred_id)
    result = svc.passkey_auth_complete(
        {
            "id": cred_id,
            "rawId": cred_id,
            "response": {"signature": sig},
        },
        challenge=challenge,
    )
    assert result.session_token
    assert result.principal.email == "pk@phzyx.xyz"


@pytest.mark.unit
def test_passkey_mfa_step_up(svc: AuthService) -> None:
    p = svc.register("mfa-pk@phzyx.xyz", "longpassword1")
    public_key = "mfa-hmac-secret"
    cred_id = "cred-mfa-1"
    svc.passkey_register_begin(p.id)
    svc.passkey_register_complete(
        p.id,
        {
            "id": cred_id,
            "response": {"publicKey": public_key},
        },
    )
    # password login → mfa required
    res = svc.login("mfa-pk@phzyx.xyz", "longpassword1")
    assert res.mfa_required
    assert res.mfa_challenge_id
    opts = svc.passkey_mfa_begin(res.mfa_challenge_id)
    challenge = opts["challenge"]
    sig = sign_hmac_assertion(public_key=public_key, challenge=challenge, credential_id=cred_id)
    done = svc.passkey_auth_complete(
        {"id": cred_id, "response": {"signature": sig}},
        challenge=challenge,
        mfa_challenge_id=res.mfa_challenge_id,
    )
    assert done.session_token


@pytest.mark.unit
def test_passkey_revoke(svc: AuthService) -> None:
    p = svc.register("rev@phzyx.xyz", "longpassword1")
    svc.passkey_register_begin(p.id)
    svc.passkey_register_complete(p.id, {"id": "x", "response": {"publicKey": "s"}})
    assert svc.revoke_passkey(p.id, "x")
    assert svc.list_passkeys(p.id) == []
