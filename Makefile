# Phzyx task runner (GNU Make). Prefer `just` when installed; targets mirror Justfile.
.PHONY: default sync test test-unit test-packaging cov lint fmt fmt-check typecheck check hello hub cli pre-commit admin-check admin-e2e demo-up demo-down dbs-up dbs-down dbs-status dbs-test

default:
	@echo "Targets: sync test cov … check hello hub cli admin-check admin-e2e demo-up demo-down"
	@echo "Tip: install just (brew install just) for a richer task runner."

sync:
	uv sync --all-packages --group dev

test:
	uv run pytest -q

test-unit:
	uv run pytest -q -m unit

test-packaging:
	uv run pytest -q tests/packaging -m packaging

# Line coverage over packages/* (omit tests/web); fail-under 75 (see pyproject; ratchet up)
cov:
	uv run pytest -q --tb=short --cov --cov-report=term-missing:skip-covered --cov-report=html --cov-fail-under=75

lint:
	uv run ruff check packages tests examples

fmt:
	uv run ruff format packages tests examples
	uv run ruff check --fix packages tests examples

fmt-check:
	uv run ruff format --check packages tests examples

typecheck:
	uv run pyright

check: lint fmt-check typecheck test cov

hello:
	uv run --directory examples/hello uvicorn main:app --reload --host 127.0.0.1 --port 8000

hub:
	python3 -m http.server 4173 --directory sites/hub

cli:
	uv run phzyx

pre-commit:
	uv run pre-commit run --all-files

# AdminBoard SPA quality (diamond D1+)
admin-check:
	cd packages/admin/web && pnpm check

admin-e2e:
	cd packages/admin/web && ADMINBOARD_BASE_URL=http://127.0.0.1:9100 pnpm e2e

demo-up:
	docker compose -f examples/adminboard_live/docker-compose.yml up --build -d

demo-down:
	docker compose -f examples/adminboard_live/docker-compose.yml down

# Multi-version SQL matrix on OrbStack (start on demand; stop when done)
dbs-up:
	./scripts/dbs/up.sh $(ARGS)

dbs-down:
	./scripts/dbs/down.sh $(ARGS)

dbs-status:
	./scripts/dbs/status.sh

dbs-test:
	./scripts/dbs/test.sh $(ARGS)

# Full D1 local gate: unit demos + SPA check + header assert (demo must be up for e2e)
diamond-d1:
	uv run pytest -q tests/demo -m unit --tb=short
	$(MAKE) admin-check
	@echo "Start demo with: make demo-up  then: make admin-e2e"
