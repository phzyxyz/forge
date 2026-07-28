# phzyx-admin

**Not a separate PyPI project** — ships inside **`phzyx-forge`**. Use `uv add 'phzyx-forge[sqlite]==0.1.0'`.


AdminBoard core: resources, AdminService, export/copy, storage, file opener.

SPA sources: `web/` (Vite + React + TanStack Query + Zustand). Build:

```bash
cd packages/admin/web && pnpm install && pnpm build
```

Output: `web/dist` mounted by `phzyx-admin-fastapi` at **`/admin/`** and **API Board** at **`/apiboard/`**.

## API Board

Forge API Client for the current server — OpenAPI collection, try-it console, environments (`{{baseUrl}}`), sandbox vs workspace JSON (`phzyx.forge.client` v1).

- UI: `web/src/features/apidocs/forgeClient/`
- Mount: `AdminBoard(..., mount_apiboard=True)` in `phzyx-admin-fastapi`
- Docs: `/forge/apiboard`
