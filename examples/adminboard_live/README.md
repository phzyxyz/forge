# AdminBoard live demo (OrbStack / Docker)

Full-featured AdminBoard SPA + FastAPI + SQLite, with **in-app login**.

## Open

| | |
|--|--|
| **URL** | http://localhost:9100/admin/ |
| **Username** | `admin` |
| **Password** | `phzyx` |

No browser system dialog for the SPA — use the **Sign in** page in AdminBoard.  
Auth is **phzyx-auth** cookie sessions (`POST /auth/login`) + CSRF on mutations; staff superuser via `PhzyxAuthz`.

Public (no auth): http://localhost:9100/health

## Run (OrbStack)

From monorepo root:

```bash
# rebuild SPA when UI changes
cd packages/admin/web && pnpm build && cd -

docker compose -f examples/adminboard_live/docker-compose.yml up --build -d
```

## What you get

- Overview dashboard (stats, quick open, activity)
- Resource tables (Users / Memberships / Assets) with search, sort, selection
- Create / edit / delete in a right **drawer**
- Export & copy under **⋯ overflow menu** (not a button farm)
- Bulk bar for multi-select delete/copy
- Media library view for file keys
- Settings: Magical White / Stellar Dark / Ambient, density
- ⌘K command palette

## Database

SQLite at `/data/demo.db` (Docker volume). **Rich seed** (v4): ~1.7k+ rows across every demo table and auth table.

| Resource | Approx rows | Notes |
|----------|-------------|--------|
| Users | 90 | team, title, country, score, last_seen |
| Organizations | 12 | plan, seats, MRR |
| Memberships | ~180 | org↔user, roles |
| Posts | 160 | status, published, views, FK author |
| Tags / PostTag | 40 / ~560 | M2M multi-select |
| Comments | 220 | FK post + author |
| Projects / members | 40 / ~180 | budgets, priorities |
| Invoices | 60 | billing stress |
| Assets | 48 | file keys + gallery media |
| Auth tables | groups, perms, sessions, API keys, audit, OAuth, MFA | browsable in admin |

**Reseed (required after schema/seed bumps):**

```bash
# Docker: wipe volume data once
PHZYX_DEMO_RESEED=1 docker compose -f examples/adminboard_live/docker-compose.yml up --build -d

# Local
PHZYX_DEMO_RESEED=1 PHZYX_DEMO_DB=./demo.db uv run uvicorn main:app --reload --port 9100
```

Optional density: `PHZYX_DEMO_N_USERS=150`, `PHZYX_DEMO_N_POSTS=300`, etc.

## Quality gates (dashboard v2)

```bash
cd packages/admin/web && pnpm check   # lint + unit + build
# with compose up on :9100:
cd packages/admin/web && ADMINBOARD_BASE_URL=http://127.0.0.1:9100 pnpm e2e
```

Playwright covers: sign in → overview → users drawer CRUD → export menu → media → sign out.

### Notes

- API 401 responses intentionally **omit** `WWW-Authenticate` (SPA owns login).  
- Booleans use checkbox widgets in the drawer.  
- Export overflow: CSV / JSON / Excel.  
- Session activity is client-only (server audit viewer later).

## Without Docker

```bash
# monorepo root, after uv sync + pnpm build of admin web
cd examples/adminboard_live
uv run uvicorn main:app --reload --host 127.0.0.1 --port 9100
```
