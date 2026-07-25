# Phzyx hello example

Minimal **FastAPI** app that imports workspace packages (`phzyx.schema`, `phzyx.admin.fastapi`) to prove monorepo wiring.

AdminBoard mount arrives in **M4** — this example stays a thin stub until then.

## Run (from monorepo root)

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
