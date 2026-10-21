"""FastAPI adapter — mount_auth, middleware, Depends, cookie sessions, CSRF, WS."""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from phzyx.auth.csrf import csrf_valid, extract_csrf, issue_csrf_token, should_check_csrf
from phzyx.auth.errors import AuthError, ForbiddenError, UnauthorizedError
from phzyx.auth.guards import (
    ensure_authenticated,
    ensure_permissions,
    ensure_scopes,
    ensure_staff,
    ensure_superuser,
)
from phzyx.auth.principal import Principal
from phzyx.auth.service import AuthService

try:
    from fastapi import APIRouter, Depends, Request, Response
    from fastapi.responses import JSONResponse
except ImportError:  # pragma: no cover
    APIRouter = Any  # type: ignore[misc, assignment]
    Depends = None  # type: ignore[misc, assignment]
    Request = Any  # type: ignore[misc, assignment]
    Response = Any  # type: ignore[misc, assignment]
    JSONResponse = Any  # type: ignore[misc, assignment]


def _principal_from_request(request: Any) -> Principal | None:
    state = getattr(request, "state", None)
    if state is None:
        return None
    p = getattr(state, "principal", None)
    return p if isinstance(p, Principal) else None


def _client_ip(request: Any) -> str | None:
    if request is None or not hasattr(request, "client") or request.client is None:
        return None
    return request.client.host


async def optional_user(request: Request) -> Principal | None:
    return _principal_from_request(request)


async def require_user(request: Request) -> Principal:
    return ensure_authenticated(_principal_from_request(request))


async def require_staff_user(request: Request) -> Principal:
    return ensure_staff(_principal_from_request(request))


async def require_superuser_user(request: Request) -> Principal:
    return ensure_superuser(_principal_from_request(request))


def require_permissions(*codes: str, any_of: bool = False) -> Callable[..., Any]:
    async def _dep(request: Request) -> Principal:
        return ensure_permissions(_principal_from_request(request), codes, any_of=any_of)

    return _dep


def require_scopes(*scopes: str, any_of: bool = False) -> Callable[..., Any]:
    async def _dep(request: Request) -> Principal:
        return ensure_scopes(_principal_from_request(request), scopes, any_of=any_of)

    return _dep


require_staff = require_staff_user
require_superuser = require_superuser_user


def get_principal(request: Request) -> Principal:
    p = _principal_from_request(request)
    if p is None:
        raise UnauthorizedError()
    return p


def attach_principal_middleware(app: Any, service: AuthService) -> None:
    """Resolve principal + optional CSRF check on mutating cookie requests."""

    @app.middleware("http")
    async def _auth_middleware(request: Request, call_next: Any) -> Any:
        cookie = request.cookies.get(service.config.session_cookie_name)
        authz = request.headers.get("authorization")
        api_key = request.headers.get("x-api-key")
        try:
            principal = service.resolve_principal(
                session_token=cookie,
                authorization=authz,
                api_key=api_key,
            )
        except Exception:
            principal = None
        request.state.principal = principal
        request.state.auth_service = service

        # Bearer / API key are not CSRF-vulnerable the same way; only session cookie.
        if should_check_csrf(
            request.method,
            has_session_cookie=bool(cookie) and not authz and not api_key,
            csrf_protect=service.config.csrf_protect,
        ):
            # Exempt login/register/forgot/reset (no session yet or recovery flows)
            path = request.url.path if hasattr(request, "url") else ""
            exempt_suffixes = (
                "/login",
                "/register",
                "/password/forgot",
                "/password/reset",
                "/refresh",
            )
            if not any(path.endswith(s) for s in exempt_suffixes):
                c_tok, h_tok = extract_csrf(
                    request,
                    cookie_name=service.config.csrf_cookie_name,
                    header_name=service.config.csrf_header_name,
                )
                if not csrf_valid(c_tok, h_tok):
                    return JSONResponse(
                        ForbiddenError("CSRF validation failed").to_dict(),
                        status_code=403,
                    )

        return await call_next(request)


def _set_session_cookie(response: Response, service: AuthService, token: str) -> None:
    cfg = service.config
    response.set_cookie(
        key=cfg.session_cookie_name,
        value=token,
        httponly=cfg.cookie_httponly,
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,  # type: ignore[arg-type]
        max_age=cfg.session_ttl_seconds,
        path="/",
    )


def _set_csrf_cookie(response: Response, service: AuthService) -> str:
    token = issue_csrf_token()
    cfg = service.config
    response.set_cookie(
        key=cfg.csrf_cookie_name,
        value=token,
        httponly=False,  # SPA must read and echo in header
        secure=cfg.cookie_secure,
        samesite=cfg.cookie_samesite,  # type: ignore[arg-type]
        max_age=cfg.session_ttl_seconds,
        path="/",
    )
    return token


def _clear_session_cookie(response: Response, service: AuthService) -> None:
    response.delete_cookie(service.config.session_cookie_name, path="/")
    response.delete_cookie(service.config.csrf_cookie_name, path="/")


def _auth_error_response(exc: AuthError) -> Any:
    return JSONResponse(exc.to_dict(), status_code=exc.status)


def create_auth_router(service: AuthService, *, prefix: str = "/auth") -> Any:
    """Build APIRouter with register/login/logout/me/reset/jwt/api-keys/email."""
    router = APIRouter(prefix=prefix, tags=["auth"])

    @router.post("/register")
    async def register(body: dict[str, Any]) -> Any:
        try:
            p = service.register(
                str(body.get("email") or ""),
                str(body.get("password") or ""),
                username=body.get("username"),
            )
            return {
                "id": p.id,
                "email": p.email,
                "is_staff": p.is_staff,
            }
        except AuthError as exc:
            return _auth_error_response(exc)
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation_error", "message": str(exc), "details": {}}},
                status_code=422,
            )

    @router.post("/login")
    async def login(body: dict[str, Any], request: Request, response: Response) -> Any:
        try:
            # Django-style: accept email, username, or generic login/identity.
            identity = (
                body.get("email")
                or body.get("username")
                or body.get("login")
                or body.get("identity")
                or ""
            )
            result = service.login(
                str(identity),
                str(body.get("password") or ""),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                issue_jwt=bool(body.get("issue_jwt")),
            )
            if result.session_token:
                _set_session_cookie(response, service, result.session_token)
                csrf = _set_csrf_cookie(response, service)
            else:
                csrf = None
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
            if csrf:
                out["csrf_token"] = csrf
            if result.tokens:
                out["access_token"] = result.tokens.access_token
                out["refresh_token"] = result.tokens.refresh_token
                out["token_type"] = result.tokens.token_type
                out["expires_in"] = result.tokens.expires_in
            return out
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/logout")
    async def logout(request: Request, response: Response) -> Any:
        cookie = request.cookies.get(service.config.session_cookie_name)
        service.logout(cookie)
        _clear_session_cookie(response, service)
        return {"ok": True}

    @router.get("/me")
    async def me(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
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

    @router.post("/password/forgot")
    async def forgot(body: dict[str, Any], request: Request) -> Any:
        raw = service.request_password_reset(str(body.get("email") or ""), ip=_client_ip(request))
        out: dict[str, Any] = {"ok": True}
        if raw and not service.config.production:
            out["dev_token"] = raw
        return out

    @router.post("/password/reset")
    async def reset(body: dict[str, Any]) -> Any:
        try:
            service.reset_password(
                str(body.get("token") or ""),
                str(body.get("new_password") or ""),
            )
            return {"ok": True}
        except AuthError as exc:
            return _auth_error_response(exc)
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation_error", "message": str(exc), "details": {}}},
                status_code=422,
            )

    @router.post("/password/change")
    async def change_password(body: dict[str, Any], request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            service.change_password(
                p.id,
                str(body.get("current_password") or ""),
                str(body.get("new_password") or ""),
                revoke_sessions=bool(body.get("revoke_sessions", True)),
            )
            return {"ok": True}
        except AuthError as exc:
            return _auth_error_response(exc)
        except ValueError as exc:
            return JSONResponse(
                {"error": {"code": "validation_error", "message": str(exc), "details": {}}},
                status_code=422,
            )

    @router.post("/sessions/revoke-all")
    async def revoke_sessions(request: Request, response: Response) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        n = service.revoke_all_sessions(p.id)
        _clear_session_cookie(response, service)
        return {"ok": True, "revoked": n}

    @router.post("/email/request-verify")
    async def request_verify(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            raw = service.request_email_verification(p.id)
            out: dict[str, Any] = {"ok": True}
            if not service.config.production:
                out["dev_token"] = raw
            return out
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/email/verify")
    async def verify_email(body: dict[str, Any]) -> Any:
        try:
            service.verify_email(str(body.get("token") or ""))
            return {"ok": True}
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/refresh")
    async def refresh(body: dict[str, Any]) -> Any:
        try:
            pair = service.refresh_jwt(str(body.get("refresh_token") or ""))
            return {
                "access_token": pair.access_token,
                "refresh_token": pair.refresh_token,
                "token_type": pair.token_type,
                "expires_in": pair.expires_in,
            }
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.get("/api-keys")
    async def list_keys(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        return {"keys": service.list_api_keys(p.id)}

    @router.post("/api-keys")
    async def create_key(body: dict[str, Any], request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            issued = service.create_api_key(
                name=str(body.get("name") or "default"),
                user_id=p.id,
                scopes=list(body.get("scopes") or []),
            )
            return {
                "id": issued.id,
                "name": issued.name,
                "prefix": issued.prefix,
                "raw_key": issued.raw_key,
                "scopes": issued.scopes,
            }
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.delete("/api-keys/{key_id}")
    async def delete_key(key_id: str, request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        ok = service.revoke_api_key(key_id, user_id=p.id)
        if not ok:
            return _auth_error_response(UnauthorizedError("API key not found"))
        return {"ok": True}

    # ── OAuth ──────────────────────────────────────────────────────────────

    @router.get("/oauth/{provider}/start")
    async def oauth_start(provider: str, request: Request) -> Any:
        try:
            redirect_uri = str(
                request.query_params.get("redirect_uri")
                or str(request.url).split("?")[0].replace("/start", "/callback")
            )
            scopes_raw = request.query_params.get("scopes")
            scopes = scopes_raw.split() if scopes_raw else None
            data = service.oauth_start(provider, redirect_uri=redirect_uri, scopes=scopes)
            accept = (request.headers.get("accept") or "").lower()
            if "application/json" in accept or request.query_params.get("format") == "json":
                return data
            from fastapi.responses import RedirectResponse

            return RedirectResponse(url=data["authorization_url"], status_code=302)
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.get("/oauth/{provider}/callback")
    async def oauth_callback(provider: str, request: Request, response: Response) -> Any:
        try:
            code = str(request.query_params.get("code") or "")
            state = str(request.query_params.get("state") or "")
            redirect_uri = request.query_params.get("redirect_uri")
            result = service.oauth_callback(
                provider,
                code=code,
                state=state,
                redirect_uri=redirect_uri,
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                issue_jwt=request.query_params.get("issue_jwt") in {"1", "true", "yes"},
            )
            if result.session_token:
                _set_session_cookie(response, service, result.session_token)
                csrf = _set_csrf_cookie(response, service)
            else:
                csrf = None
            out: dict[str, Any] = {
                "id": result.principal.id,
                "email": result.principal.email,
                "is_staff": result.principal.is_staff,
                "auth_method": result.principal.auth_method,
            }
            if csrf:
                out["csrf_token"] = csrf
            if result.tokens:
                out["access_token"] = result.tokens.access_token
                out["refresh_token"] = result.tokens.refresh_token
            return out
        except AuthError as exc:
            return _auth_error_response(exc)

    # ── MFA / TOTP ─────────────────────────────────────────────────────────

    @router.post("/mfa/totp/setup")
    async def mfa_setup(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            return service.mfa_totp_setup(p.id)
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/mfa/totp/confirm")
    async def mfa_confirm(body: dict[str, Any], request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            service.mfa_totp_confirm(p.id, str(body.get("code") or ""))
            return {"ok": True, "mfa_enabled": True}
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/mfa/totp/verify")
    async def mfa_verify(body: dict[str, Any], request: Request, response: Response) -> Any:
        try:
            result = service.mfa_totp_verify_challenge(
                str(body.get("mfa_challenge_id") or body.get("challenge_id") or ""),
                str(body.get("code") or ""),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
            if result.session_token:
                _set_session_cookie(response, service, result.session_token)
                csrf = _set_csrf_cookie(response, service)
            else:
                csrf = None
            out: dict[str, Any] = {
                "id": result.principal.id,
                "email": result.principal.email,
                "is_staff": result.principal.is_staff,
                "is_superuser": result.principal.is_superuser,
            }
            if csrf:
                out["csrf_token"] = csrf
            if result.tokens:
                out["access_token"] = result.tokens.access_token
                out["refresh_token"] = result.tokens.refresh_token
            return out
        except AuthError as exc:
            return _auth_error_response(exc)

    # ── Passkeys / WebAuthn ────────────────────────────────────────────────

    @router.post("/passkeys/register/begin")
    async def passkey_reg_begin(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            return service.passkey_register_begin(p.id)
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/passkeys/register/complete")
    async def passkey_reg_complete(body: dict[str, Any], request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        try:
            cred = body.get("credential") or body
            return service.passkey_register_complete(p.id, dict(cred))
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/passkeys/auth/begin")
    async def passkey_auth_begin(body: dict[str, Any] | None = None) -> Any:
        body = body or {}
        try:
            return service.passkey_auth_begin(
                email=body.get("email"),
                user_id=body.get("user_id"),
            )
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/passkeys/auth/complete")
    async def passkey_auth_complete(
        body: dict[str, Any], request: Request, response: Response
    ) -> Any:
        try:
            result = service.passkey_auth_complete(
                dict(body.get("credential") or body),
                challenge=body.get("challenge"),
                mfa_challenge_id=body.get("mfa_challenge_id"),
                issue_jwt=bool(body.get("issue_jwt")),
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent"),
            )
            if result.session_token:
                _set_session_cookie(response, service, result.session_token)
                csrf = _set_csrf_cookie(response, service)
            else:
                csrf = None
            out: dict[str, Any] = {
                "id": result.principal.id,
                "email": result.principal.email,
                "is_staff": result.principal.is_staff,
                "is_superuser": result.principal.is_superuser,
            }
            if csrf:
                out["csrf_token"] = csrf
            if result.tokens:
                out["access_token"] = result.tokens.access_token
                out["refresh_token"] = result.tokens.refresh_token
            return out
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.post("/passkeys/mfa/begin")
    async def passkey_mfa_begin(body: dict[str, Any]) -> Any:
        try:
            return service.passkey_mfa_begin(
                str(body.get("mfa_challenge_id") or body.get("challenge_id") or "")
            )
        except AuthError as exc:
            return _auth_error_response(exc)

    @router.get("/passkeys")
    async def passkey_list(request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        return {"keys": service.list_passkeys(p.id)}

    @router.delete("/passkeys/{credential_id}")
    async def passkey_delete(credential_id: str, request: Request) -> Any:
        p = _principal_from_request(request)
        if p is None:
            return _auth_error_response(UnauthorizedError())
        ok = service.revoke_passkey(p.id, credential_id)
        if not ok:
            return _auth_error_response(UnauthorizedError("Passkey not found"))
        return {"ok": True}

    return router


def mount_auth(
    app: Any,
    service: AuthService,
    *,
    prefix: str = "/auth",
    middleware: bool = True,
) -> AuthService:
    """Attach middleware + auth routes to a FastAPI app."""
    if middleware:
        attach_principal_middleware(app, service)
    app.include_router(create_auth_router(service, prefix=prefix))
    app.state.phzyx_auth = service
    return service


async def websocket_principal(websocket: Any, service: AuthService | None = None) -> Principal:
    """Authenticate WebSocket from cookie / Authorization / API key.

    Closes with 4401 if unauthenticated.
    """
    auth_service: AuthService | None = service
    if auth_service is None:
        app = getattr(websocket, "app", None)
        state = getattr(app, "state", None) if app is not None else None
        if state is not None:
            candidate = getattr(state, "phzyx_auth", None)
            if isinstance(candidate, AuthService):
                auth_service = candidate
    if auth_service is None:
        await websocket.close(code=4401)
        raise UnauthorizedError()

    cookies = {}
    with contextlib.suppress(Exception):
        cookies = websocket.cookies
    cookie = cookies.get(auth_service.config.session_cookie_name) if cookies else None
    headers = getattr(websocket, "headers", {}) or {}
    authz = None
    api_key = None
    if hasattr(headers, "get"):
        authz = headers.get("authorization")
        api_key = headers.get("x-api-key")
    principal = auth_service.resolve_principal(
        session_token=cookie,
        authorization=authz,
        api_key=api_key,
    )
    if principal is None:
        await websocket.close(code=4401)
        raise UnauthorizedError()
    return principal
