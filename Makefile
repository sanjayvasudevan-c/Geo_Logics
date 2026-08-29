# SatQuery — developer targets.
# Everything runs through `uv`, which provisions the pinned interpreter and environment.

UV := uv

.PHONY: help setup lint typecheck test test-unit test-integration coverage check clean reproduce

help:
	@echo "setup       install the pinned environment (uv sync --extra dev)"
	@echo "lint        ruff check on src/ and tests/"
	@echo "typecheck   mypy --strict on src/satquery"
	@echo "test        full pytest run"
	@echo "test-unit   pytest -m unit"
	@echo "coverage    pytest with coverage report"
	@echo "check       lint + typecheck + test"
	@echo "reproduce   rebuild the pipeline from a clean environment (CLAUDE.md §8)"

setup:
	$(UV) sync --extra dev

lint:
	$(UV) run ruff check src tests

typecheck:
	$(UV) run mypy

test:
	$(UV) run pytest

test-unit:
	$(UV) run pytest -m unit

test-integration:
	$(UV) run pytest -m integration

coverage:
	$(UV) run pytest --cov --cov-report=term-missing

check: lint typecheck test

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# CLAUDE.md §8 requires `make reproduce` to rebuild the pipeline from a clean environment.
# Stage 1 provides the entry point; stages that add pipeline steps extend it.
reproduce:
	@echo "make reproduce is not implemented yet — no pipeline stages exist as of Stage S1."
	@echo "It will be extended as stages land. Failing loudly rather than pretending to succeed."
	@exit 1
