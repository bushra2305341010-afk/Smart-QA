.PHONY: install up down lint fmt typecheck test-fast test-int test cov doctor prod-config prod-up prod-migrate smoke backup

install:        ## install deps + git hooks
	uv sync
	uv run pre-commit install

up:             ## start infra (db, redis, s3) and api
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

# ---------- production (docs/23 §9) ----------
PROD = docker compose -f deploy/compose.prod.yml --env-file .env.production

prod-config:    ## validate the production compose file and .env.production
	$(PROD) config -q && echo "compose OK"

prod-up:        ## build/pull and start the production stack (runs migrations first)
	$(PROD) up -d --build

prod-migrate:   ## run database migrations only
	$(PROD) run --rm migrate

smoke:          ## post-deploy smoke test: make smoke URL=https://qa.example.com
	deploy/scripts/smoke.sh $(URL)

backup:         ## database backup into ./backups (keep 14)
	deploy/scripts/backup.sh ./backups
