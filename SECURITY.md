# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| 0.1.x   | Yes (current public line) |
| 1.x     | Not released yet |
| other   | Best effort only |

## Reporting a vulnerability

**Do not open a public GitHub issue for security problems.**

Email the steward: **security@phzyx.xyz** (or the GitHub security advisory form once the repo is public and Advisories are enabled).

Please include:

- Affected package(s) and version(s)
- Description and impact
- Reproduction steps or a minimal PoC
- Whether you have a suggested fix

You should receive an acknowledgment within a few days (solo maintainer — best effort). Coordinated disclosure is preferred.

## Scope

In scope: authentication/authorization bypass in AdminBoard adapters, SQL injection in ORM/engine helpers we ship, unsafe defaults that ship enabled, supply-chain issues in published wheels.

Out of scope: vulnerabilities in third-party drivers (psycopg, redis, etc.), misconfiguration of host apps, or using `AllowAll` authz in production.

## Hardening notes (operators)

- Never deploy AdminBoard with `AllowAll` authz.
- Prefer HTTPS + CSP (mounted by default on admin routes).
- Store file **keys** in the DB; use storage backends with authz on upload/download.
- Pin release versions (`phzyx==0.1.x` or individual `phzyx-*` pins).
