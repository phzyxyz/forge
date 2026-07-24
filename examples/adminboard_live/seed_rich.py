"""Large realistic seed for AdminBoard live demo (every demo + auth table)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta
from typing import Any

# Bump when schema or seed density changes — triggers wipe + full reseed.
SEED_SCHEMA_VERSION = 5

FIRST = [
    "Ava",
    "Noah",
    "Maya",
    "Jordan",
    "Samira",
    "Eli",
    "Riley",
    "Casey",
    "Priya",
    "Alex",
    "Sofia",
    "Liam",
    "Zoe",
    "Marcus",
    "Nina",
    "Omar",
    "Ivy",
    "Kai",
    "Lena",
    "Theo",
    "Amara",
    "Diego",
    "Hana",
    "Felix",
    "Yuki",
    "Nora",
    "Jasper",
    "Leila",
    "Owen",
    "Sana",
    "Mateo",
    "Chloe",
    "Ibrahim",
    "Aria",
    "Hugo",
    "Mei",
    "Ravi",
    "Elena",
    "Finn",
    "Aisha",
    "Leo",
    "Camille",
    "Darius",
    "Tara",
    "Nico",
    "Freya",
    "Omar",
    "Sloane",
    "Beau",
    "Ines",
]
LAST = [
    "Chen",
    "Lee",
    "Okonkwo",
    "Park",
    "Nguyen",
    "Brooks",
    "Shah",
    "Rivera",
    "Patel",
    "Kim",
    "Garcia",
    "Silva",
    "Andersen",
    "Kowalski",
    "Müller",
    "Dubois",
    "Rossi",
    "Tanaka",
    "Singh",
    "Costa",
    "Berg",
    "Hassan",
    "Novak",
    "Okafor",
    "Petrov",
    "Johansson",
    "Wong",
    "Almeida",
    "Ivanova",
    "Moreau",
    "Khan",
    "Sato",
    "Fischer",
    "Andersen",
    "Larsen",
    "Santos",
    "Haddad",
]
TEAMS = [
    "Platform",
    "Product",
    "Security",
    "Data",
    "Customer Success",
    "Design",
    "DevRel",
    "Finance",
    "Growth",
    "Infra",
    "QA",
    "Docs",
]
TITLES = [
    "Engineer",
    "Senior Engineer",
    "Staff Engineer",
    "Designer",
    "PM",
    "Ops Lead",
    "Analyst",
    "Security Engineer",
    "SRE",
    "Support",
    "Intern",
    "Director",
]
COUNTRIES = [
    "US",
    "CA",
    "GB",
    "DE",
    "FR",
    "IN",
    "BR",
    "JP",
    "AU",
    "NL",
    "SE",
    "SG",
    "NG",
    "MX",
    "KR",
]
POST_STATUSES = ["draft", "review", "published", "archived"]
ROLES = ["admin", "member", "viewer", "service", "billing", "owner"]
TAG_POOL = [
    ("platform", "Platform"),
    ("security", "Security"),
    ("product", "Product"),
    ("ops", "Ops"),
    ("onboarding", "Onboarding"),
    ("migrations", "Migrations"),
    ("orm", "ORM"),
    ("adminboard", "AdminBoard"),
    ("auth", "Auth"),
    ("media", "Media"),
    ("export", "Export"),
    ("filters", "Filters"),
    ("relations", "Relations"),
    ("m2m", "M2M"),
    ("fastapi", "FastAPI"),
    ("litestar", "Litestar"),
    ("postgres", "Postgres"),
    ("sqlite", "SQLite"),
    ("mysql", "MySQL"),
    ("cli", "CLI"),
    ("performance", "Performance"),
    ("a11y", "Accessibility"),
    ("themes", "Themes"),
    ("audit", "Audit"),
    ("passkeys", "Passkeys"),
    ("oauth", "OAuth"),
    ("mfa", "MFA"),
    ("billing", "Billing"),
    ("docs", "Docs"),
    ("dx", "DX"),
    ("ci", "CI"),
    ("release", "Release"),
    ("hotfix", "Hotfix"),
    ("rfc", "RFC"),
    ("design", "Design"),
    ("research", "Research"),
    ("customer", "Customer"),
    ("internal", "Internal"),
    ("public", "Public"),
    ("beta", "Beta"),
]
COLORS = [
    "#22d3ee",
    "#8b5cf6",
    "#4ade80",
    "#fb923c",
    "#f472b6",
    "#60a5fa",
    "#facc15",
    "#34d399",
    "#a78bfa",
    "#f87171",
]


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _email(i: int, first: str, last: str) -> str:
    if i == 1:
        return "ops@phzyx.xyz"
    if i == 2:
        return "dev@phzyx.xyz"
    if i == 3:
        return "guest@phzyx.xyz"
    if i == 12:
        return "bot+ci@phzyx.xyz"
    slug = f"{first}.{last}".lower().replace("ü", "u").replace(" ", "")
    domain = "phzyx.xyz" if i <= 15 else "northwind.example"
    return f"{slug}{i}@{domain}"


def build_users(n: int = 90) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    base = date(2022, 1, 1)
    for i in range(1, n + 1):
        first = FIRST[(i - 1) % len(FIRST)]
        last = LAST[(i * 3) % len(LAST)]
        if i == 1:
            name, notes = "Ava Operations", "Platform ops · on-call lead · US/Pacific"
        elif i == 2:
            name, notes = "Noah Developer", "Full-stack · AdminBoard SPA · Stellar Dark"
        elif i == 3:
            name, notes = "Guest Preview", "Deactivated sandbox for demos"
        elif i == 12:
            name, notes = "CI Bot", "Service account for e2e · do not delete"
        else:
            name = f"{first} {last}"
            notes = (
                f"{TITLES[i % len(TITLES)]} on {TEAMS[i % len(TEAMS)]} · "
                f"prefers {'Magical White' if i % 2 else 'Stellar Dark'} · "
                f"handles tickets #{1000 + i}"
            )
        active = i not in {3, 9, 27, 41, 63} and i % 17 != 0
        joined = None if i == 3 else base + timedelta(days=(i * 11) % 1400)
        rows.append(
            {
                "id": i,
                "email": _email(i, first, last),
                "name": name,
                "active": active,
                "joined": joined,
                "notes": notes,
                "team": TEAMS[i % len(TEAMS)],
                "title": TITLES[i % len(TITLES)],
                "country": COUNTRIES[i % len(COUNTRIES)],
                "score": (i * 7) % 100,
                "last_seen": None
                if not active
                else datetime(2026, 1, 1) + timedelta(days=i % 200, hours=i % 24),
            }
        )
    return rows


def build_orgs(n: int = 12) -> list[dict[str, Any]]:
    plans = ["free", "pro", "business", "enterprise"]
    names = [
        "Platform Core",
        "Customer Success",
        "Brand Studio",
        "Northwind Retail",
        "Acme Labs",
        "Orbital Health",
        "Pixel Forge",
        "Harbor Logistics",
        "Cedar Finance",
        "Summit Analytics",
        "Blue River Media",
        "Quanta Research",
        "Helios Cloud",
        "Moss & Co",
        "Atlas Robotics",
    ]
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "name": names[(i - 1) % len(names)] if i <= len(names) else f"Org {i}",
                "slug": f"org-{i}",
                "plan": plans[i % len(plans)],
                "seats": 5 + (i * 3) % 90,
                "active": i % 11 != 0,
                "region": COUNTRIES[i % len(COUNTRIES)],
                "mrr_cents": (i * 1299) % 500_000,
                "created_on": date(2023, 1, 1) + timedelta(days=i * 17),
            }
        )
    return rows


def build_memberships(user_n: int, org_n: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    # dense: each user in 1–3 orgs
    for uid in range(1, user_n + 1):
        for k in range(1 + uid % 3):
            oid = 1 + ((uid + k * 5) % org_n)
            role = ROLES[(uid + k) % len(ROLES)]
            rows.append(
                {
                    "org_id": oid,
                    "user_id": uid,
                    "role": role,
                    "since": date(2023, 6, 1) + timedelta(days=(uid * 3 + k * 40) % 900),
                    "primary": k == 0,
                }
            )
    # dedupe composite pk
    seen: set[tuple[int, int]] = set()
    out = []
    for r in rows:
        key = (r["org_id"], r["user_id"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def build_tags() -> list[dict[str, Any]]:
    rows = []
    for i, (slug, name) in enumerate(TAG_POOL, start=1):
        rows.append(
            {
                "id": i,
                "name": name,
                "slug": slug,
                "color": COLORS[(i - 1) % len(COLORS)],
                "description": f"Topics tagged {name.lower()} across the demo corpus.",
                "featured": i <= 8 or i % 5 == 0,
            }
        )
    return rows


def build_posts(n: int = 160, user_n: int = 90) -> list[dict[str, Any]]:
    titles = [
        "Welcome to AdminBoard",
        "Shipping Diamond relations",
        "Filter OS tips",
        "Media library refresh",
        "Auth session persistence",
        "Export playbook",
        "Onboarding checklist",
        "Security review notes",
        "Org structure walkthrough",
        "CI bot guardrails",
        "Keyset pagination deep dive",
        "M2M multi-select patterns",
        "Theme gallery pass",
        "Schema status page",
        "Plugin SPI hello world",
        "Passkeys pilot",
        "OAuth Google wiring",
        "Redis rate limits",
        "MySQL dialect baseline",
        "Production hardening notes",
    ]
    rows = []
    for i in range(1, n + 1):
        author = 1 + (i * 3) % max(1, user_n)
        status = POST_STATUSES[i % len(POST_STATUSES)]
        published = status == "published"
        body = (
            f"Post #{i}: {titles[(i - 1) % len(titles)]}. "
            f"Author user_id={author}. Status={status}. "
            "Use filters, FK author autocomplete, relation panels, and M2M tags. "
            f"Paragraph for textarea widget · lorem demo {i * 13}."
        )
        rows.append(
            {
                "id": i,
                "title": f"{titles[(i - 1) % len(titles)]} (#{i})",
                "author_id": author,
                "body": body,
                "status": status,
                "published": published,
                "published_at": date(2024, 1, 1) + timedelta(days=i * 2) if published else None,
                "views": (i * 37) % 50_000,
                "featured": i % 11 == 0,
                "summary": f"Summary for post {i}: diamond demo content for AdminBoard.",
            }
        )
    return rows


def build_post_tags(post_n: int, tag_n: int) -> list[dict[str, Any]]:
    rows = []
    seen: set[tuple[int, int]] = set()
    for pid in range(1, post_n + 1):
        # 2–5 tags each
        for k in range(2 + pid % 4):
            tid = 1 + ((pid * 5 + k * 7) % tag_n)
            key = (pid, tid)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"post_id": pid, "tag_id": tid})
    return rows


def build_assets(n: int = 48) -> list[dict[str, Any]]:
    kinds = ["image", "document", "avatar", "banner", "upload", "diagram"]
    paths = [
        "brand/logo.svg",
        "brand/wordmark.svg",
        "marketing/hero.svg",
        "marketing/banner.svg",
        "avatars/ops.svg",
        "avatars/dev.svg",
        "docs/readme.txt",
        "docs/changelog.md",
        "uploads/sample-notes.txt",
    ]
    # generate extra path keys that seed media will create
    for i in range(1, 40):
        paths.append(f"uploads/doc-{i:03d}.txt")
        paths.append(f"gallery/tile-{i:03d}.svg")
    rows = []
    for i in range(1, n + 1):
        path = paths[(i - 1) % len(paths)]
        rows.append(
            {
                "id": i,
                "title": f"Asset {i}: {path.split('/')[-1]}",
                "path": path,
                "kind": kinds[i % len(kinds)],
                "size_bytes": 400 + (i * 997) % 900_000,
                "uploaded_by": 1 + (i % 40),
                "public": i % 3 != 0,
                "caption": f"Seeded media object #{i} for library thumbs and file widgets.",
            }
        )
    return rows


def build_comments(n: int = 220, post_n: int = 160, user_n: int = 90) -> list[dict[str, Any]]:
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "post_id": 1 + (i * 2) % post_n,
                "author_id": 1 + (i * 5) % user_n,
                "body": (
                    f"Comment #{i}: looks good — please check filters on this post. "
                    f"Also verify M2M tags still round-trip after save ({i})."
                ),
                "approved": i % 4 != 0,
                "created_at": datetime(2025, 6, 1) + timedelta(hours=i * 3),
                "likes": (i * 3) % 120,
            }
        )
    return rows


def build_projects(n: int = 40, user_n: int = 90) -> list[dict[str, Any]]:
    statuses = ["planned", "active", "blocked", "done"]
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "name": f"Project {chr(64 + (i % 26) or 26)}-{i:02d}",
                "owner_id": 1 + (i * 2) % user_n,
                "status": statuses[i % len(statuses)],
                "budget_usd": 5_000 + (i * 2500) % 200_000,
                "due_date": date(2026, 3, 1) + timedelta(days=i * 5),
                "priority": 1 + (i % 5),
                "description": f"Cross-functional initiative #{i} for AdminBoard stress data.",
            }
        )
    return rows


def build_project_members(project_n: int, user_n: int) -> list[dict[str, Any]]:
    rows = []
    seen: set[tuple[int, int]] = set()
    for pid in range(1, project_n + 1):
        for k in range(3 + pid % 4):
            uid = 1 + ((pid * 4 + k * 9) % user_n)
            key = (pid, uid)
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "project_id": pid,
                    "user_id": uid,
                    "role": ROLES[k % len(ROLES)],
                    "allocation_pct": 10 + (k * 15) % 90,
                }
            )
    return rows


def build_invoices(n: int = 60, org_n: int = 12) -> list[dict[str, Any]]:
    statuses = ["draft", "open", "paid", "void", "past_due"]
    rows = []
    for i in range(1, n + 1):
        rows.append(
            {
                "id": i,
                "org_id": 1 + (i % org_n),
                "number": f"INV-2026-{i:04d}",
                "amount_cents": 9900 + (i * 137) % 250_000,
                "currency": ["USD", "EUR", "GBP", "INR"][i % 4],
                "status": statuses[i % len(statuses)],
                "issued_on": date(2025, 1, 1) + timedelta(days=i * 3),
                "due_on": date(2025, 1, 15) + timedelta(days=i * 3),
                "memo": f"Subscription + seats for period {i}",
            }
        )
    return rows


def build_auth_seed() -> dict[str, list[dict[str, Any]]]:
    """Non-secret-looking demo rows for auth tables (hashes are fake but unique)."""
    now = datetime(2026, 7, 1, 12, 0, 0)
    groups = [
        {"id": 1, "name": "Administrators", "slug": "admins"},
        {"id": 2, "name": "Editors", "slug": "editors"},
        {"id": 3, "name": "Viewers", "slug": "viewers"},
        {"id": 4, "name": "Billing", "slug": "billing"},
        {"id": 5, "name": "Support", "slug": "support"},
    ]
    perms = []
    codes = [
        "users:list",
        "users:create",
        "users:update",
        "users:delete",
        "posts:list",
        "posts:create",
        "posts:update",
        "posts:delete",
        "media:upload",
        "export:run",
        "audit:read",
        "settings:write",
        "orgs:admin",
        "billing:read",
        "billing:write",
    ]
    for i, code in enumerate(codes, start=1):
        perms.append({"id": i, "code": code, "label": code.replace(":", " · ")})

    ug = [
        {"user_id": 1, "group_id": 1},
        {"user_id": 1, "group_id": 2},
        {"user_id": 2, "group_id": 2},
        {"user_id": 2, "group_id": 3},
        {"user_id": 3, "group_id": 3},
    ]
    # more memberships for demo auth user ids if present later — seed against auth users separately

    gp = []
    for gid, prange in ((1, range(1, 16)), (2, range(5, 11)), (3, range(5, 7)), (4, range(13, 16))):
        for pid in prange:
            gp.append({"group_id": gid, "permission_id": pid})

    up = [
        {"user_id": 1, "permission_id": 11},
        {"user_id": 2, "permission_id": 9},
    ]

    sessions = []
    for i in range(1, 25):
        sessions.append(
            {
                "id": i,
                "token_hash": _hash(f"session-{i}-{secrets.token_hex(4)}"),
                "user_id": 1 + (i % 5),
                "expires_at": now + timedelta(days=7 + i),
                "idle_expires_at": now + timedelta(hours=12),
                "revoked_at": now - timedelta(days=1) if i % 9 == 0 else None,
                "user_agent": f"Mozilla/5.0 DemoBrowser/{i}.0",
                "ip_hash": _hash(f"10.0.0.{i}")[:32],
                "created_at": now - timedelta(days=i),
            }
        )

    refresh = []
    for i in range(1, 16):
        refresh.append(
            {
                "id": i,
                "jti_hash": _hash(f"jti-{i}"),
                "family_id": f"fam-{(i % 4) + 1}",
                "user_id": 1 + (i % 4),
                "expires_at": now + timedelta(days=30),
                "revoked_at": None if i % 5 else now,
                "scopes": "openid profile email",
                "created_at": now - timedelta(days=i),
            }
        )

    api_keys = []
    for i in range(1, 12):
        prefix = f"phx_demo_{i:02d}"
        api_keys.append(
            {
                "id": i,
                "name": f"Demo key {i}",
                "prefix": prefix,
                "key_hash": _hash(f"{prefix}-secret"),
                "user_id": 1 if i < 6 else 2,
                "scopes": "admin:read admin:write" if i % 2 else "admin:read",
                "expires_at": now + timedelta(days=365) if i % 3 else None,
                "revoked_at": now if i == 11 else None,
                "last_used_at": now - timedelta(hours=i * 3),
                "created_at": now - timedelta(days=i * 2),
            }
        )

    resets = []
    for i in range(1, 8):
        resets.append(
            {
                "id": i,
                "token_hash": _hash(f"reset-{i}"),
                "user_id": 1 + (i % 4),
                "expires_at": now + timedelta(hours=2),
                "used_at": now - timedelta(hours=1) if i % 2 == 0 else None,
                "attempts": i % 3,
                "created_at": now - timedelta(hours=i),
            }
        )

    audit = []
    events = [
        "login.success",
        "login.failed",
        "logout",
        "password.reset",
        "api_key.created",
        "mfa.enabled",
        "oauth.linked",
        "session.revoked",
    ]
    for i in range(1, 80):
        audit.append(
            {
                "id": i,
                "event_type": events[i % len(events)],
                "actor_id": str(1 + (i % 6)),
                "ip_hash": _hash(f"ip-{i}")[:24],
                "meta_json": f'{{"demo":true,"n":{i}}}',
                "created_at": now - timedelta(hours=i * 2),
            }
        )

    oauth = []
    for i, prov in enumerate(["google", "github", "google", "github", "microsoft"], start=1):
        oauth.append(
            {
                "id": i,
                "provider": prov,
                "provider_user_id": f"{prov}-user-{i}",
                "user_id": i,
                "email": f"oauth{i}@example.com",
                "granted_scopes": "email profile",
                "access_token_enc": None,
                "refresh_token_enc": None,
                "created_at": now - timedelta(days=i * 10),
                "updated_at": now - timedelta(days=i),
            }
        )

    mfa = []
    for i in range(1, 6):
        mfa.append(
            {
                "id": i,
                "user_id": i,
                "kind": "totp" if i % 2 else "webauthn",
                "secret_encrypted": _hash(f"mfa-secret-{i}")[:32],
                "label": f"Device {i}",
                "verified": i != 5,
                "created_at": now - timedelta(days=20 + i),
                "verified_at": now - timedelta(days=i) if i != 5 else None,
            }
        )

    return {
        "groups": groups,
        "permissions": perms,
        "user_groups": ug,
        "group_permissions": gp,
        "user_permissions": up,
        "sessions": sessions,
        "refresh_tokens": refresh,
        "api_keys": api_keys,
        "password_resets": resets,
        "audit": audit,
        "oauth": oauth,
        "mfa": mfa,
    }


def extra_media_files() -> dict[str, str]:
    """Path → text body for media seed beyond the core set."""
    files: dict[str, str] = {}
    for i in range(1, 40):
        files[f"uploads/doc-{i:03d}.txt"] = (
            f"Demo document {i}\n"
            f"================\n"
            f"Generated seed file for AdminBoard media library testing.\n"
            f"Use filters, preview, and download flows.\n"
        )
        files[f"gallery/tile-{i:03d}.svg"] = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">'
            f'<rect width="160" height="160" rx="16" fill="{COLORS[i % len(COLORS)]}"/>'
            f'<text x="80" y="90" text-anchor="middle" font-size="28" fill="#041018">'
            f"{i}</text></svg>"
        )
    return files
