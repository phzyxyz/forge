"""Refresh rotation stays in one family and replays a lost response."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from phzyx.auth.ids import uuid7
from phzyx.auth.principal import Principal
from phzyx.auth.tokens import JwtService


def _principal() -> Principal:
    return Principal(id="7", email="a@b.co", auth_method="password")


@pytest.mark.unit
def test_uuid7_is_a_version_7_string() -> None:
    text = uuid7()
    assert text[14] == "7"
    assert text[19] in "89ab"


@pytest.mark.unit
def test_refresh_keeps_family_and_replays_receipt() -> None:
    jwt = JwtService(secret="refresh-receipt-secret-key-32b!!", refresh_grace=30)
    first = jwt.issue_pair(_principal())
    stored = jwt.refresh_store.get(first.refresh_token, secret=jwt.secret)
    assert stored is not None
    family = stored["family_id"]
    assert family[14] == "7"

    rotated = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    assert rotated.refresh_token != first.refresh_token
    again = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert again is not None
    assert again["family_id"] == family

    replayed = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    assert replayed.access_token == rotated.access_token
    assert replayed.refresh_token == rotated.refresh_token


@pytest.mark.unit
def test_refresh_reuse_after_grace_revokes_family() -> None:
    jwt = JwtService(secret="refresh-receipt-secret-key-32b!!", refresh_grace=30)
    first = jwt.issue_pair(_principal())
    rotated = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    record = jwt.refresh_store._by_jti
    old_hash = next(h for h, rec in record.items() if rec.get("raw_jti") == first.refresh_token)
    record[old_hash]["receipt_until"] = datetime.now(UTC) - timedelta(seconds=1)

    with pytest.raises(ValueError, match="invalid_refresh"):
        jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    live = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert live is not None and live["revoked"]
