# Phzyx hello example

Minimal **FastAPI** app that imports workspace packages to prove Forge wiring.

For a **full scaffolded app** (async CRUD + AdminBoard + forge island), use:

```bash
uv run phzyx new myapp --preset max
```

Or follow [Getting started](https://phzyx.xyz/forge/getting-started).  
Rich operator demo: `examples/adminboard_live/`.

## Run (from forge repo root)

```bash
# Prefer the task runner (uses root uv env where packages are already installed)
make hello
# or: just hello

# Manual
uv run --directory examples/hello uvicorn main:app --reload --port 8000
```

Then open <http://127.0.0.1:8000/> — you should see package versions in JSON.

## Standalone example env (optional)

```bash
cd examples/hello
uv sync
uv run uvicorn main:app --reload
```

Path dependencies point at `../../packages/*`.

## Expected evolution

```python
from phzyx.orm import Model, Field
from phzyx.admin.fastapi import AdminBoard

# class User(Model): ...
# AdminBoard(app, models=[User], theme="magical-white")
```
