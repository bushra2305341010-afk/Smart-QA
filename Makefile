.PHONY: install up down lint fmt typecheck test-fast test-int test cov doctor

install:        ## install deps + git hooks
	uv sync
	uv run pre-commit install

up:             ## start infra (db, redis, minio) and api
	docker compose up -d --build

down:
	docker compose down

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

typecheck:
	uv run mypy

test-fast:      ## unit tests, no services needed
	uv run pytest -m "not integration"

test-int:       ## integration tests (needs: docker compose up -d db redis)
	uv run pytest -m integration

test: lint typecheck test-fast

cov:
	uv run pytest -m "not integration" --cov --cov-report=term-missing

doctor:         ## quick environment check
	@uv --version && docker --version && docker compose version
	@curl -fsS http://localhost:8000/api/v1/readyz && echo
