"""Litestar adapter — mount_auth_litestar, middleware, login/register/me."""

from __future__ import annotations

import contextlib
from typing import Any

from phzyx.auth.csrf import issue_csrf_token
from phzyx.auth.errors import AuthError, UnauthorizedError
from phzyx.auth.principal import Principal
from phzyx.auth.service import AuthService

try:
    from litestar import MediaType, Request, Response, Router, get, post

    _HAS_LITESTAR = True
except ImportError:  # pragma: no cover
    _HAS_LITESTAR = False
    MediaType = Any  # type: ignore[misc, assignment]
    Request = Any  # type: ignore[misc, assignment]
    Response = Any  # type: ignore[misc, assignment]
    Router = Any  # type: ignore[misc, assignment]
    get = post = None  # type: ignore[misc, assignment]


def _require_litestar() -> None:
    if not _HAS_LITESTAR:
        raise ImportError("Litestar adapter requires litestar — install phzyx-auth[litestar]")


def _principal_from_connection(connection: Any) -> Principal | None:
    state = getattr(connection, "state", None)
    if state is None:
        return None
    if isinstance(state, dict):
        p = state.get("principal")
    else:
        p = getattr(state, "principal", None)
        if p is None and hasattr(state, "get"):
            try:
                p = state.get("principal")
            except Exception:
                p = None
    return p if isinstance(p, Principal) else None


def _client_ip(request: Any) -> str | None:
    client = getattr(request, "client", None)
    if client is None:
        return None
    return getattr(client, "host", None) or (
        client[0] if isinstance(client, (list, tuple)) else None
    )


def _apply_session_cookies(response: Any, service: AuthService, token: str) -> str:
    cfg = service.config
    response.set_cookie(
        key=cfg.session_cookie_name,
        value=token,
        httponly=cfg.cookie_httponly,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,
        max_age=cfg.session_ttl_seconds,
        path="/",
    )
    csrf = issue_csrf_token()
    response.set_cookie(
        key=cfg.csrf_cookie_name,
        value=csrf,
        httponly=False,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,
        max_age=cfg.session_ttl_seconds,
        path="/",
    )
    return csrf


def _clear_session_cookies(response: Any, service: AuthService) -> None:
    response.delete_cookie(service.config.session_cookie_name, path="/")
    response.delete_cookie(service.config.csrf_cookie_name, path="/")


def _err(exc: AuthError) -> Any:
    return Response(content=exc.to_dict(), status_code=exc.status, media_type=MediaType.JSON)


def create_auth_router_litestar(service: AuthService, *, prefix: str = "/auth") -> Any:
    """Build Litestar Router with register/login/logout/me (same paths as FastAPI)."""
    _require_litestar()
    path_prefix = prefix.rstrip("/") or "/auth"

    @post("/register")
    async def register(data: dict[str, Any]) -> Any:
        try:
            p = service.register(
                str(data.get("email") or ""),
                str(data.get("password") or ""),
                username=data.get("username"),
            )
            return {
                "id": p.id,
                "email": p.email,
                "is_staff": p.is_staff,
            }
        except AuthError as exc:
            return _err(exc)
        except ValueError as ve:
            return Response(
                content={
                    "error": {
                        "code": "validation_error",
                        "message": str(ve),
                        "details": {},
                    }
                },
                status_code=422,
                media_type=MediaType.JSON,
            )

    @post("/login")
    async def login(data: dict[str, Any], request: Request) -> Any:
        try:
            result = service.login(
                str(data.get("email") or ""),
                str(data.get("password") or ""),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                issue_jwt=bool(data.get("issue_jwt")),
            )
            out: dict[str, Any] = {
                "id": result.principal.id,
                "email": result.principal.email,
                "is_staff": result.principal.is_staff,
                "is_superuser": result.principal.is_superuser,
                "permissions": sorted(result.principal.permissions),
            }
            if result.mfa_challenge_id:
                out["mfa_required"] = True
                out["mfa_challenge_id"] = result.mfa_challenge_id
            if result.tokens:
                out["access_token"] = result.tokens.access_token
                out["refresh_token"] = result.tokens.refresh_token
                out["token_type"] = result.tokens.token_type
                out["expires_in"] = result.tokens.expires_in
            if result.session_token:
                resp = Response(content=out, status_code=200, media_type=MediaType.JSON)
                csrf = _apply_session_cookies(resp, service, result.session_token)
                # rebuild body with csrf after cookie side-effect
                resp.content = {**out, "csrf_token": csrf}
                return resp
            return out
        except AuthError as exc:
            return _err(exc)

    @post("/logout")
    async def logout(request: Request) -> Any:
        cookie = request.cookies.get(service.config.session_cookie_name)
        service.logout(cookie)
        resp = Response(content={"ok": True}, status_code=200, media_type=MediaType.JSON)
        _clear_session_cookies(resp, service)
        return resp

    @get("/me")
    async def me(request: Request) -> Any:
        p = _principal_from_connection(request)
        if p is None:
            return _err(UnauthorizedError())
        return {
            "id": p.id,
            "email": p.email,
            "username": p.username,
            "is_staff": p.is_staff,
            "is_superuser": p.is_superuser,
            "permissions": sorted(p.permissions),
            "scopes": sorted(p.scopes),
            "auth_method": p.auth_method,
        }

    return Router(
        path=path_prefix,
        route_handlers=[register, login, logout, me],
        tags=["auth"],
    )


def principal_middleware_factory(service: AuthService) -> Any:
    """Return a pure ASGI middleware class bound to ``service``."""
    _require_litestar()

    class PrincipalASGIMiddleware:
        def __init__(self, app: Any) -> None:
            self.app = app

        async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
            if scope.get("type") in {"http", "websocket"}:
                headers = {
                    k.decode("latin-1").lower(): v.decode("latin-1")
                    for k, v in (scope.get("headers") or [])
                }
                cookie_header = headers.get("cookie", "")
                cookies: dict[str, str] = {}
                for part in cookie_header.split(";"):
                    part = part.strip()
                    if "=" in part:
                        k, v = part.split("=", 1)
                        cookies[k.strip()] = v.strip()
                cookie = cookies.get(service.config.session_cookie_name)
                authz = headers.get("authorization")
                api_key = headers.get("x-api-key")
                try:
                    principal = service.resolve_principal(
                        session_token=cookie,
                        authorization=authz,
                        api_key=api_key,
                    )
                except Exception:
                    principal = None
                state = scope.setdefault("state", {})
                if isinstance(state, dict):
                    state["principal"] = principal
                    state["auth_service"] = service
                else:
                    try:
                        state.principal = principal  # type: ignore[attr-defined]
                        state.auth_service = service  # type: ignore[attr-defined]
                    except Exception:
                        scope["state"] = {
                            "principal": principal,
                            "auth_service": service,
                        }
            await self.app(scope, receive, send)

    return PrincipalASGIMiddleware


def attach_principal_middleware_litestar(app: Any, service: AuthService) -> None:
    """Register principal middleware on a Litestar app (best-effort if already built)."""
    _require_litestar()
    mw_cls = principal_middleware_factory(service)
    mw = list(getattr(app, "middleware", None) or [])
    mw.insert(0, mw_cls)
    try:
        app.middleware = mw
    except Exception:
        app._phzyx_auth_middleware = mw_cls  # type: ignore[attr-defined]


def mount_auth_litestar(
    app: Any,
    service: AuthService,
    *,
    prefix: str = "/auth",
    middleware: bool = True,
) -> AuthService:
    """Attach principal middleware + auth routes to a Litestar app.

    Prefer constructing the app with the router when possible::

        from phzyx.auth.adapters.litestar import create_auth_router_litestar
        app = Litestar(route_handlers=[create_auth_router_litestar(svc)])

    Raises ``ImportError`` if litestar is not installed.
    """
    _require_litestar()
    router = create_auth_router_litestar(service, prefix=prefix)
    app.register(router)

    if middleware:
        attach_principal_middleware_litestar(app, service)

    state = getattr(app, "state", None)
    if state is not None:
        if isinstance(state, dict):
            state["phzyx_auth"] = service
        else:
            with contextlib.suppress(Exception):
                state.phzyx_auth = service
    return service
