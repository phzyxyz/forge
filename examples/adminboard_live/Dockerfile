# Phzyx AdminBoard live demo — build from monorepo root:
#   docker compose -f examples/adminboard_live/docker-compose.yml up --build
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Minimal monorepo surface for uv workspace + SPA assets
COPY pyproject.toml uv.lock ./
COPY packages/schema packages/schema
COPY packages/engine packages/engine
COPY packages/orm packages/orm
COPY packages/auth packages/auth
COPY packages/admin packages/admin
COPY packages/admin-fastapi packages/admin-fastapi
COPY packages/cli packages/cli
COPY packages/cache packages/cache
COPY packages/admin-litestar packages/admin-litestar
COPY packages/meta packages/meta
COPY examples/adminboard_live examples/adminboard_live

# Install workspace (editable) without dev tools + ASGI server
RUN uv sync --all-packages --no-dev \
    && uv pip install uvicorn \
    && test -f packages/admin/web/dist/index.html

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PHZYX_ADMIN_USER=admin \
    PHZYX_ADMIN_PASSWORD=phzyx \
    PHZYX_ADMIN_THEME=stellar-dark \
    PHZYX_DEMO_DB=/data/demo.db \
    PHZYX_DEMO_MEDIA=/data/media

RUN mkdir -p /data/media

WORKDIR /app/examples/adminboard_live
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
