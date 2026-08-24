CONTAINER_NAME = plateforme-accueil

.PHONY: help db dev embed-test test lint fmt deploy

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-10s %s\n", $$1, $$2}'

db: ## Start the local PostgreSQL container
	docker compose up -d

dev: ## Run the dev server on :8000
	DEBUG=1 uv run python manage.py runserver

embed-test: ## Serve the fake host page on :8001 (needs `make dev` on :8000)
	uv run python -m http.server 8001 --directory docs/embed-test

test: ## Run the test suite
	uv run pytest

lint: ## Ruff check + format check
	uv run ruff check .
	uv run ruff format --check .

fmt: ## Ruff auto-format
	uv run ruff format .
	uv run ruff check --fix .

deploy: ## Build, push and redeploy the Scaleway container (needs SCW_REGISTRY)
	@test -n "$$SCW_REGISTRY" || { echo "error: SCW_REGISTRY not set"; exit 1; }
	docker buildx build --platform linux/amd64 -t "$$SCW_REGISTRY/$(CONTAINER_NAME):latest" . --push
	@container_id=$$(scw container container list name=$(CONTAINER_NAME) -o json | jq -r '.[0].id'); \
	test -n "$$container_id" && test "$$container_id" != "null" || { echo "error: no container named $(CONTAINER_NAME)"; exit 1; }; \
	scw container container redeploy "$$container_id" region=fr-par
