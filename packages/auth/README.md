# phzyx-auth

Secure-by-default authentication & authorization for Phzyx apps and AdminBoard.

**Public battery** for Forge (depends on `phzyx-forge` on PyPI).

```bash
uv add 'phzyx-forge[auth]==0.1.0'
# or
uv add 'phzyx-auth[fastapi]==0.1.0'
```

## Status (0.1.0)

**Phase A + B shipped** (memory backends; ORM-backed stores next):

| Area | What you get |
|------|----------------|
| Passwords | Argon2id, policy min length |
| Sessions | Opaque cookie sessions (hashed at rest), idle + absolute TTL |
| JWT | HS256 access + rotating refresh |
| API keys | `phx_` prefix, scopes, list/revoke |
| RBAC | Groups/Permissions models, Principal, `ensure_*` + Depends + decorators |
| Lockout | Failed-login counter + rate limits + audit log |
| Reset / change | Forgot/reset (anti-enum), change password, revoke sessions |
| Email verify | Token issue + verify (`email_verified` flag) |
| CSRF | Double-submit cookie + `X-CSRF-Token` for session mutations |
| WebSocket | `websocket_principal` (cookie / Bearer / API key, close 4401) |
| AdminBoard | `PhzyxAuthz` permission bridge |
| CLI | `phzyx-auth create-superuser` |

**Later:** OAuth IdPs (Phase D stub in `oauth.py`), MFA/passkeys (E), orgs (F), Redis rate limit, ORM session store.

## Quick start (FastAPI)

```python
from fastapi import Depends, FastAPI
from phzyx.auth import AuthConfig, AuthService, Principal
from phzyx.auth.adapters.fastapi import mount_auth, require_user

app = FastAPI()
svc = AuthService(
    config=AuthConfig(
        secret="use-PHZYX_AUTH_SECRET-32+bytes-in-prod!!",
        production=False,
        cookie_secure=False,
    )
)
mount_auth(app, svc)

@app.get("/private")
async def private(user: Principal = Depends(require_user)):
    return {"email": user.email}
```

```bash
# create staff superuser (in-memory unless you wire persistence)
phzyx-auth create-superuser --email admin@example.com --password 'longpassword1'
```

### SPA cookie flow

1. `POST /auth/login` → sets `phzyx_session` (HttpOnly) + `phzyx_csrf` + returns `csrf_token`
2. Mutating requests with the session cookie must send header `X-CSRF-Token: <csrf_token>`
3. Bearer JWT / `X-API-Key` skip CSRF

### In-body checks (no middleware)

```python
from phzyx.auth.guards import ensure_authenticated, ensure_permissions

p = svc.resolve_principal(session_token=cookie, authorization=authz, api_key=key)
user = ensure_authenticated(p)
ensure_permissions(user, ["posts:create"])
```

## Security defaults

- Argon2id hashing  
- Secrets ≥ 32 bytes (HS256 / pepper)  
- Opaque sessions + short JWT access  
- API keys hashed at rest  
- Lockout + IP/email rate limits  
- Password reset anti-enumeration  
- Extensible `AbstractUser`  

**Research (do not re-derive):** [`research/plan/20_phzyx_auth.md`](../../research/plan/20_phzyx_auth.md)  
**Tracker:** [`PHZYX_ROADMAP.html`](../../PHZYX_ROADMAP.html) track **AUTH**.
