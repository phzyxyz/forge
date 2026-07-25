# phzyx-admin

AdminBoard core: resources, AdminService, export/copy, storage, file opener.

SPA sources: `web/` (Vite + React + TanStack Query + Zustand). Build:

```bash
cd packages/admin/web && npm install && npm run build
```

Output: `web/dist` mounted by `phzyx-admin-fastapi`.
