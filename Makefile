.PHONY: install up down logs status clean

install: ## Install CLI dependencies
	uv sync
	@echo ""
	@echo "CLI installed. Use with:"
	@echo "  uv run adwize <command>"
	@echo "  or: source .venv/bin/activate && adwize <command>"

up: ## Start all services
	docker compose up -d --build

down: ## Stop all services
	docker compose down

logs: ## Tail service logs
	docker compose logs -f

status: ## Check API health
	@curl -sf http://localhost:8000/health | python3 -m json.tool 2>/dev/null || echo "API is not running. Run: make up"

clean: ## Remove volumes and venv
	docker compose down -v
	rm -rf .venv

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
