# Developer convenience targets. Run `make help` for the list.
# Works on macOS/Linux; on Windows use Git Bash or WSL, or run the underlying
# commands directly.

.DEFAULT_GOAL := help
PY ?= python

.PHONY: help install install-py install-js test test-py lint typecheck \
        build-dashboard build-ts up down seed evals fmt

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-py install-js ## Install everything for local dev

install-py: ## Editable-install the Python packages with dev extras
	$(PY) -m pip install -e packages/evaluators
	$(PY) -m pip install -e "packages/sdk-python[dev]"
	$(PY) -m pip install -e "server[dev]"

install-js: ## Install dashboard + TS SDK deps
	cd dashboard && npm install
	cd packages/sdk-typescript && npm install

test: test-py ## Run all tests
	cd packages/sdk-typescript && npm test

test-py: ## Run the Python test suites
	pytest packages/sdk-python packages/evaluators server

lint: ## Lint Python (ruff)
	ruff check packages server evals examples

typecheck: ## Type-check the Python SDK (mypy)
	cd packages/sdk-python && mypy sentinel

build-dashboard: ## Build the dashboard
	cd dashboard && npm run build

build-ts: ## Build the TypeScript SDK
	cd packages/sdk-typescript && npm run build

up: ## Start the full stack via Docker
	docker compose up --build

down: ## Stop the stack
	docker compose down

seed: ## Seed demo traces into a running collector (no API keys)
	$(PY) examples/quickstart/seed_demo.py

evals: ## Run the offline eval suite
	$(PY) evals/run_evals.py --dataset evals/datasets/factual_qa.jsonl

fmt: ## Auto-format/fix Python lint issues
	ruff check --fix packages server evals examples
