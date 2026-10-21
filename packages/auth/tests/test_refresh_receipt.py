"""Refresh rotation stays in one family.

The retry key is Refresh-Request-Id, not a clock. The same id returns
the pair from the first call. A different id, or no id, revokes the family.
"""

from __future__ import annotations

import pytest
from phzyx.auth.ids import uuid7
from phzyx.auth.principal import Principal
from phzyx.auth.tokens import JwtService

_SECRET = "refresh-receipt-secret-key-32b!!"


def _principal() -> Principal:
    return Principal(id="7", email="a@b.co", auth_method="password")


def _jwt() -> JwtService:
    return JwtService(secret=_SECRET)


@pytest.mark.unit
def test_uuid7_is_a_version_7_string() -> None:
    text = uuid7()
    assert text[14] == "7"
    assert text[19] in "89ab"


@pytest.mark.unit
def test_same_request_id_returns_the_first_successor() -> None:
    jwt = _jwt()
    first = jwt.issue_pair(_principal())
    stored = jwt.refresh_store.get(first.refresh_token, secret=jwt.secret)
    assert stored is not None
    family = stored["family_id"]
    assert family[14] == "7"

    rotated = jwt.refresh(
        first.refresh_token,
        principal_loader=lambda _uid: _principal(),
        request_id="retry-1",
    )
    assert rotated.refresh_token != first.refresh_token
    again = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert again is not None
    assert again["family_id"] == family

    replayed = jwt.refresh(
        first.refresh_token,
        principal_loader=lambda _uid: _principal(),
        request_id="retry-1",
    )
    assert replayed.access_token == rotated.access_token
    assert replayed.refresh_token == rotated.refresh_token


@pytest.mark.unit
def test_different_request_id_revokes_the_family() -> None:
    jwt = _jwt()
    first = jwt.issue_pair(_principal())
    rotated = jwt.refresh(
        first.refresh_token,
        principal_loader=lambda _uid: _principal(),
        request_id="retry-1",
    )

    with pytest.raises(ValueError, match="invalid_refresh"):
        jwt.refresh(
            first.refresh_token,
            principal_loader=lambda _uid: _principal(),
            request_id="retry-2",
        )
    live = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert live is not None and live["revoked"]


@pytest.mark.unit
def test_missing_request_id_on_a_consumed_token_revokes_the_family() -> None:
    jwt = _jwt()
    first = jwt.issue_pair(_principal())
    rotated = jwt.refresh(
        first.refresh_token,
        principal_loader=lambda _uid: _principal(),
        request_id="retry-1",
    )

    with pytest.raises(ValueError, match="invalid_refresh"):
        jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    live = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert live is not None and live["revoked"]


@pytest.mark.unit
def test_two_callers_without_a_request_id_cannot_replay() -> None:
    """An empty id never matches an empty id."""
    jwt = _jwt()
    first = jwt.issue_pair(_principal())
    rotated = jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())

    with pytest.raises(ValueError, match="invalid_refresh"):
        jwt.refresh(first.refresh_token, principal_loader=lambda _uid: _principal())
    live = jwt.refresh_store.get(rotated.refresh_token, secret=jwt.secret)
    assert live is not None and live["revoked"]
