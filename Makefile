# Development targets
# -------------

.PHONY: sync
sync:
	uv sync

.PHONY: start
start:
	uv run uvicorn src.main:app --reload

.PHONY: start-relay
start-relay:
	uv run python -m src.relay

# Lint & Format
# -------------

.PHONY: lint
lint:
	uv run ruff check

.PHONY: format
format:
	uv run ruff format
	uv run ruff check --fix

.PHONY: check-types
check-types:
	uv run mypy src --install-types --non-interactive

.PHONY: test
test:
	uv run pytest

.PHONY: setup-precommit
setup-precommit:
	uv run pre-commit install

.PHONY: check-precommit
check-precommit:
	uv run pre-commit run --all-files

.PHONY: check-all
check-all: lint check-types test

.PHONY: generate-migration
generate-migration:
	@read -p "Описание миграции: " message; \
	uv run alembic revision --autogenerate -m "$$message"

.PHONY: migrate
migrate:
	uv run alembic upgrade head

.PHONY: rollback
rollback:
	uv run alembic downgrade -1

# Docker
# -------------

.PHONY: dc-up
dc-up:
	docker compose up -d

.PHONY: dc-down
dc-down:
	docker compose down

.PHONY: dc-logs
dc-logs:
	docker compose logs -f
