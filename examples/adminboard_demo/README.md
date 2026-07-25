# AdminBoard demo

```bash
# from monorepo root
uv sync --all-packages
# build SPA once
cd packages/admin/web && npm run build && cd -

uv run --with uvicorn uvicorn examples.adminboard_demo.main:app --app-dir . --reload --port 8000
```

Open:

- API: http://127.0.0.1:8000/admin/api/v1/resources  
- SPA: http://127.0.0.1:8000/admin/ (after SPA build)  
- OpenAPI: http://127.0.0.1:8000/docs  

Themes: Magical White + Stellar Dark switcher in the sidebar (preference in `localStorage`).
