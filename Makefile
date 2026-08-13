# Single entrypoint for humans and CI. `make check` is what CI runs.
.DEFAULT_GOAL := help
UV  ?= uv
RUN ?= $(UV) run

.PHONY: help install lint format type test check run clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install:  ## Sync all extras + dev tools into the uv venv, and pre-commit hooks
	$(UV) sync --all-extras
	$(RUN) pre-commit install

lint:  ## Ruff lint + yamllint on config
	$(RUN) ruff check src tests
	$(RUN) yamllint config

format:  ## Auto-format with ruff
	$(RUN) ruff format src tests

type:  ## Static type check
	$(RUN) mypy

test:  ## Run the test suite with coverage
	$(RUN) pytest --cov=agentic_blog --cov-report=term-missing

check: lint type test  ## What CI runs (and pre-push)

run:  ## Run the CLI: make run ARGS="run book.pdf --topic obs --render blog,skill"
	$(RUN) agentic-blog $(ARGS)

clean:  ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
