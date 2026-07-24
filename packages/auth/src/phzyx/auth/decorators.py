"""Decorators for sync and async callables — require auth / permissions / scopes."""

from __future__ import annotations

import functools
import inspect
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

from phzyx.auth.errors import UnauthorizedError
from phzyx.auth.guards import (
    ensure_authenticated,
    ensure_permissions,
    ensure_scopes,
    ensure_staff,
    ensure_superuser,
)
from phzyx.auth.principal import Principal

P = ParamSpec("P")
R = TypeVar("R")


def _extract_principal(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Principal | None:
    if "principal" in kwargs and kwargs["principal"] is not None:
        p = kwargs["principal"]
        return p if isinstance(p, Principal) else None
    for a in args:
        if isinstance(a, Principal):
            return a
        state = getattr(a, "state", None)
        if state is not None:
            p = getattr(state, "principal", None)
            if isinstance(p, Principal):
                return p
        p = getattr(a, "principal", None)
        if isinstance(p, Principal):
            return p
    return None


def _wrap(fn: Callable[P, R], check: Callable[[Principal | None], Principal]) -> Callable[P, R]:
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def async_inner(*args: P.args, **kwargs: P.kwargs) -> R:
            check(_extract_principal(args, kwargs))
            return await fn(*args, **kwargs)  # type: ignore[misc]

        return async_inner  # type: ignore[return-value]

    @functools.wraps(fn)
    def sync_inner(*args: P.args, **kwargs: P.kwargs) -> R:
        check(_extract_principal(args, kwargs))
        return fn(*args, **kwargs)

    return sync_inner


def require_auth(fn: Callable[P, R] | None = None) -> Any:
    """Require authenticated principal (sync or async view)."""

    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        return _wrap(f, ensure_authenticated)

    if fn is not None:
        return decorator(fn)
    return decorator


def require_staff(fn: Callable[P, R] | None = None) -> Any:
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        return _wrap(f, ensure_staff)

    if fn is not None:
        return decorator(fn)
    return decorator


def require_superuser(fn: Callable[P, R] | None = None) -> Any:
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        return _wrap(f, ensure_superuser)

    if fn is not None:
        return decorator(fn)
    return decorator


def require_permissions(
    *codes: str, any_of: bool = False
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        def check(p: Principal | None) -> Principal:
            return ensure_permissions(p, codes, any_of=any_of)

        return _wrap(f, check)

    return decorator


def require_scopes(
    *scopes: str, any_of: bool = False
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    def decorator(f: Callable[P, R]) -> Callable[P, R]:
        def check(p: Principal | None) -> Principal:
            return ensure_scopes(p, scopes, any_of=any_of)

        return _wrap(f, check)

    return decorator


def get_principal_or_401(principal: Principal | None) -> Principal:
    if principal is None:
        raise UnauthorizedError()
    return ensure_authenticated(principal)
