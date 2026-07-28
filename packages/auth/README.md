# Phzyx Auth

Secure-by-default **identity, sessions, JWT, API keys, and RBAC** for Forge apps and AdminBoard.

This is an **optional battery**. Most apps start with:

```bash
uv add phzyx-forge
uv add 'phzyx-forge[auth]'
# or: uv add phzyx-auth
```

---

## Full docs live on the website

PyPI is the install surface. Tutorials, production notes, and product context are on **phzyx.xyz**:

| | |
|--|--|
| **Auth tutorial** | [https://phzyx.xyz/forge/tutorials/auth](https://phzyx.xyz/forge/tutorials/auth) |
| **Forge docs** | [https://phzyx.xyz/forge](https://phzyx.xyz/forge) |
| **Getting started** | [https://phzyx.xyz/forge/getting-started](https://phzyx.xyz/forge/getting-started) |
| **Product home** | [https://phzyx.xyz](https://phzyx.xyz) |
| **Source** | [https://github.com/phzyxyz/forge](https://github.com/phzyxyz/forge) |

**After install → open [phzyx.xyz/forge/tutorials/auth](https://phzyx.xyz/forge/tutorials/auth).**

---

## Install

```bash
uv add 'phzyx-forge[auth]'
# equivalent
uv add 'phzyx-auth[fastapi]'
```

Requires **`phzyx-forge`** (product wheel).

---

## What you get (0.1)

| Area | Capability |
|------|------------|
| Passwords | Argon2id, policy min length |
| Sessions | Opaque cookie sessions (hashed at rest), idle + absolute TTL |
| JWT | HS256 access + rotating refresh |
| API keys | `phx_` prefix, scopes, list/revoke |
| RBAC | Groups / permissions, `Principal`, guards |
| Lockout | Failed-login counter + rate limits + audit log |
| Reset / change | Forgot/reset (anti-enum), change password, revoke sessions |
| CSRF | Double-submit cookie + `X-CSRF-Token` for session mutations |
| AdminBoard | Permission bridge for staff UI |
| CLI | `phzyx-auth create-superuser` |

Pre-1.0: APIs may change. Prefer lockfiles.

---

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
phzyx-auth create-superuser --email admin@example.com --password 'longpassword1'
```

Full walkthrough: **[Auth tutorial](https://phzyx.xyz/forge/tutorials/auth)**.

---

## Related

- Product: [phzyx-forge](https://pypi.org/project/phzyx-forge/)  
- Cache battery: [phzyx-cache](https://pypi.org/project/phzyx-cache/)  
- Site: [phzyx.xyz](https://phzyx.xyz)

## License

MIT · [phzyx.xyz](https://phzyx.xyz)
