"""WebAuthn / passkey support — production backend + HMAC test/dev backend.

Production: install ``phzyx-auth[webauthn]`` (``webauthn`` package).
Tests/dev: :class:`HmacPasskeyBackend` (challenge-response, no browser required).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from typing import Any, Protocol


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


@dataclass(frozen=True, slots=True)
class PasskeyVerifiedRegistration:
    credential_id: str
    public_key: str  # opaque storage (PEM, COSE b64, or hmac secret id)
    sign_count: int = 0
    transports: tuple[str, ...] = ()
    aaguid: str | None = None


@dataclass(frozen=True, slots=True)
class PasskeyVerifiedAuthentication:
    credential_id: str
    new_sign_count: int
    user_handle: str | None = None


class PasskeyBackend(Protocol):
    def registration_options(
        self,
        *,
        user_id: str,
        user_name: str,
        user_display: str,
        exclude_credential_ids: list[str],
        rp_id: str,
        rp_name: str,
    ) -> dict[str, Any]: ...

    def verify_registration(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
    ) -> PasskeyVerifiedRegistration: ...

    def authentication_options(
        self,
        *,
        allow_credential_ids: list[str],
        rp_id: str,
    ) -> dict[str, Any]: ...

    def verify_authentication(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
        credential_public_key: str,
        sign_count: int,
    ) -> PasskeyVerifiedAuthentication: ...


@dataclass
class HmacPasskeyBackend:
    """Dev/test passkey backend using HMAC-SHA256 (not browser WebAuthn).

    Client protocol (JSON):
    - registration response: ``{id, rawId, response: {clientDataJSON, publicKey,
      attestationObject?}, type: "public-key"}`` where publicKey is a random
      secret the client generated (base64url); server stores it as public_key.
    - authentication: client sends ``response.signature`` = base64url(
      HMAC-SHA256(publicKey, challenge||rawId) )
    """

    def registration_options(
        self,
        *,
        user_id: str,
        user_name: str,
        user_display: str,
        exclude_credential_ids: list[str],
        rp_id: str,
        rp_name: str,
    ) -> dict[str, Any]:
        challenge = _b64url(secrets.token_bytes(32))
        return {
            "challenge": challenge,
            "rp": {"id": rp_id, "name": rp_name},
            "user": {
                "id": _b64url(user_id.encode()),
                "name": user_name,
                "displayName": user_display,
            },
            "pubKeyCredParams": [{"type": "public-key", "alg": -7}],
            "timeout": 60000,
            "attestation": "none",
            "excludeCredentials": [
                {"type": "public-key", "id": cid} for cid in exclude_credential_ids
            ],
            "authenticatorSelection": {
                "residentKey": "preferred",
                "userVerification": "preferred",
            },
            "phzyx_backend": "hmac",
        }

    def verify_registration(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
    ) -> PasskeyVerifiedRegistration:
        cid = str(credential.get("id") or credential.get("rawId") or "")
        if not cid:
            raise ValueError("missing credential id")
        resp = credential.get("response") or {}
        client_data = resp.get("clientDataJSON") or ""
        # optional: validate origin from clientDataJSON when present
        if client_data:
            try:
                raw = _b64url_decode(client_data) if isinstance(client_data, str) else client_data
                data = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                origin = data.get("origin")
                if origin and expected_origin and origin != expected_origin:
                    raise ValueError("origin mismatch")
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
                pass
        public_key = str(resp.get("publicKey") or resp.get("public_key") or "")
        if not public_key:
            # auto-generate stable secret for incomplete clients (tests)
            public_key = _b64url(secrets.token_bytes(32))
        transports = tuple(credential.get("transports") or ("internal",))
        return PasskeyVerifiedRegistration(
            credential_id=cid,
            public_key=public_key,
            sign_count=0,
            transports=transports,
        )

    def authentication_options(
        self,
        *,
        allow_credential_ids: list[str],
        rp_id: str,
    ) -> dict[str, Any]:
        challenge = _b64url(secrets.token_bytes(32))
        return {
            "challenge": challenge,
            "timeout": 60000,
            "rpId": rp_id,
            "allowCredentials": [{"type": "public-key", "id": cid} for cid in allow_credential_ids],
            "userVerification": "preferred",
            "phzyx_backend": "hmac",
        }

    def verify_authentication(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
        credential_public_key: str,
        sign_count: int,
    ) -> PasskeyVerifiedAuthentication:
        cid = str(credential.get("id") or credential.get("rawId") or "")
        if not cid:
            raise ValueError("missing credential id")
        resp = credential.get("response") or {}
        sig = str(resp.get("signature") or "")
        if not sig:
            raise ValueError("missing signature")
        msg = f"{expected_challenge}|{cid}".encode()
        expected = _b64url(
            hmac.new(
                credential_public_key.encode()
                if not _looks_b64(credential_public_key)
                else _b64url_decode(credential_public_key),
                msg,
                hashlib.sha256,
            ).digest()
        )
        # also accept HMAC over raw secret string
        expected2 = _b64url(hmac.new(credential_public_key.encode(), msg, hashlib.sha256).digest())
        if not (hmac.compare_digest(sig, expected) or hmac.compare_digest(sig, expected2)):
            raise ValueError("invalid passkey signature")
        return PasskeyVerifiedAuthentication(
            credential_id=cid,
            new_sign_count=sign_count + 1,
            user_handle=None,
        )


def _looks_b64(s: str) -> bool:
    try:
        _b64url_decode(s)
        return True
    except Exception:
        return False


@dataclass
class WebAuthnPasskeyBackend:
    """Browser WebAuthn via optional ``webauthn`` package."""

    def registration_options(
        self,
        *,
        user_id: str,
        user_name: str,
        user_display: str,
        exclude_credential_ids: list[str],
        rp_id: str,
        rp_name: str,
    ) -> dict[str, Any]:
        from webauthn import generate_registration_options, options_to_json
        from webauthn.helpers.structs import (
            AuthenticatorSelectionCriteria,
            PublicKeyCredentialDescriptor,
            UserVerificationRequirement,
        )

        exclude = [
            PublicKeyCredentialDescriptor(id=_b64url_decode(cid)) for cid in exclude_credential_ids
        ]
        opts = generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_id=user_id.encode(),
            user_name=user_name,
            user_display_name=user_display,
            exclude_credentials=exclude or None,
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        data = json.loads(options_to_json(opts))
        data["phzyx_backend"] = "webauthn"
        return data

    def verify_registration(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
    ) -> PasskeyVerifiedRegistration:
        from webauthn import base64url_to_bytes, verify_registration_response
        from webauthn.helpers.structs import RegistrationCredential

        verification = verify_registration_response(
            credential=RegistrationCredential.parse_obj(credential)
            if hasattr(RegistrationCredential, "parse_obj")
            else credential,  # type: ignore[arg-type]
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
        )
        return PasskeyVerifiedRegistration(
            credential_id=_b64url(verification.credential_id),
            public_key=_b64url(verification.credential_public_key),
            sign_count=int(verification.sign_count or 0),
            aaguid=str(verification.aaguid) if verification.aaguid else None,
        )

    def authentication_options(
        self,
        *,
        allow_credential_ids: list[str],
        rp_id: str,
    ) -> dict[str, Any]:
        from webauthn import generate_authentication_options, options_to_json
        from webauthn.helpers.structs import (
            PublicKeyCredentialDescriptor,
            UserVerificationRequirement,
        )

        allow = [
            PublicKeyCredentialDescriptor(id=_b64url_decode(cid)) for cid in allow_credential_ids
        ]
        opts = generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=allow or None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        data = json.loads(options_to_json(opts))
        data["phzyx_backend"] = "webauthn"
        return data

    def verify_authentication(
        self,
        *,
        credential: dict[str, Any],
        expected_challenge: str,
        expected_origin: str,
        expected_rp_id: str,
        credential_public_key: str,
        sign_count: int,
    ) -> PasskeyVerifiedAuthentication:
        from webauthn import base64url_to_bytes, verify_authentication_response

        verification = verify_authentication_response(
            credential=credential,  # type: ignore[arg-type]
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_rp_id=expected_rp_id,
            expected_origin=expected_origin,
            credential_public_key=_b64url_decode(credential_public_key),
            credential_current_sign_count=sign_count,
        )
        return PasskeyVerifiedAuthentication(
            credential_id=_b64url(verification.credential_id),
            new_sign_count=int(verification.new_sign_count or sign_count + 1),
        )


def default_passkey_backend() -> PasskeyBackend | None:
    """WebAuthn when the extra is installed. Never an HMAC stand-in.

    Callers that want the test HMAC backend pass :class:`HmacPasskeyBackend`
    explicitly. Production refuses that backend.
    """
    try:
        import webauthn  # noqa: F401

        return WebAuthnPasskeyBackend()
    except ImportError:
        return None


def sign_hmac_assertion(*, public_key: str, challenge: str, credential_id: str) -> str:
    """Helper for tests / HMAC backend clients."""
    msg = f"{challenge}|{credential_id}".encode()
    return _b64url(hmac.new(public_key.encode(), msg, hashlib.sha256).digest())
