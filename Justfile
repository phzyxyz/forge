# Phzyx task runner (https://github.com/casey/just)
# Install: brew install just  ·  Fallback: make <target>

set dotenv-load := false
set shell := ["bash", "-euo", "pipefail", "-c"]

default:
    @just --list

# Install workspace + dev tools
sync:
    uv sync --all-packages --group dev

# Run full test suite
test:
    uv run pytest -q

# Unit-marked tests only
test-unit:
    uv run pytest -q -m unit

# Packaging import/layout tests
test-packaging:
    uv run pytest -q tests/packaging -m packaging

# Line coverage (packages only; fail-under 75 → ratchet to 80+)
cov:
    uv run pytest -q --tb=short --cov --cov-report=term-missing:skip-covered --cov-report=html --cov-fail-under=75

# Ruff lint
lint:
    uv run ruff check packages tests examples

# Ruff format (write)
fmt:
    uv run ruff format packages tests examples
    uv run ruff check --fix packages tests examples

# Format check only (CI parity)
fmt-check:
    uv run ruff format --check packages tests examples

# Typecheck (pyright / D14)
typecheck:
    uv run pyright

# Lint + format check + types + tests + coverage gate (local PR gate)
check: lint fmt-check typecheck test cov

# FastAPI hello example
hello:
    uv run --directory examples/hello uvicorn main:app --reload --host 127.0.0.1 --port 8000

# Brand hub static preview
hub:
    python3 -m http.server 4173 --directory sites/hub

# CLI stub
cli:
    uv run phzyx

# pre-commit on all files
pre-commit:
    uv run pre-commit run --all-files
