# Python version
PYTHON_VERSION ?= 3.12
# venv directory
VENV ?= .venv

export UV_PYTHON=$(PYTHON_VERSION)
export UV_PROJECT_ENVIRONMENT=$(VENV)

# Main args
ARGS ?= --help

# Var dir
VAR_DIR := .var
# Output dir
OUTPUT_DIR := $(VAR_DIR)/dist
# Unit test dir
TEST_UNIT_DIR := tests/unit
# Integration test dir
TEST_INTEGRATION_DIR := tests/integration
# Github test dir
TEST_GITHUB_DIR := tests/github

# Utils
PYTHON := uv run python
PYTEST := uv run --group dev-test pytest
RUFF := uv run --group dev-lint ruff
MDFORMAT := uv run --group dev-lint mdformat
TRIVY := uv run --group dev-scan trivy
PRECOMMIT := uv run --group dev-lint pre-commit
BUMPVER := uv run --group dev-release bumpver

ifeq ($(OS),Windows_NT)
    RM = del /Q /F
    RM_S = del /S /Q /F
    RMDIR = rmdir /S /Q
define CLEAR_DEEP_CACHE
	-$(RM_S) *.pyc
	-$(RM_S) *.pyo
	-for /d /r . %d in (__pycache__ .pytest_cache .ruff_cache *.egg-info) do @if exist "%d" rmdir /s /q "%d"
endef
else
    RM = rm -f
    RMDIR = rm -rf
define CLEAR_DEEP_CACHE
	-find . -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
	-find . -type d \( -name "__pycache__" -o -name ".pytest_cache" -o -name ".ruff_cache" -o -name "*.egg-info" \) -exec rm -rf {} +
endef
endif

.PHONY: install init-dev lint lint-all format test-unit test-integration test-github scan check build run release-patch release-minor release-major clean

install:
	uv sync --group dev-lint --group dev-test --group dev-release

init-dev: install
	$(PRECOMMIT) install --install-hooks \
		-t pre-commit \
		-t post-checkout \
		-t post-merge \
		-t post-rewrite \
		-t pre-push

# Run code linters, type checkers, and spell checkers for changed files
lint:
	$(PRECOMMIT) run --hook-stage pre-commit

# Run code linters, type checkers, and spell checkers for all files
lint-all:
	$(PRECOMMIT) run --hook-stage pre-commit --all-files

# Auto-format Python code and Markdown files (with GFM plugin support)
format:
	$(RUFF) format
	$(MDFORMAT) --wrap no --plugin gfm README.md

# Run unit tests with coverage based on pytest.ini settings
test-unit:
	$(PYTEST) $(TEST_UNIT_DIR)

# Run integration tests skipping code coverage calculations
test-integration:
	$(PYTEST) $(TEST_INTEGRATION_DIR) --no-cov

# Run github actions tests skipping code coverage calculations
test-github:
	$(PYTEST) $(TEST_GITHUB_DIR) --no-cov

# Run security vulnerability and secret scanning using Trivy
scan:
	@echo "Running vulnerability and secret scanning with Trivy ..."
	$(TRIVY) fs --format table --config trivy.yml .

# Run all pre-commit checks (linting + testing + security scan)
check: lint-all test-unit scan

# Build source distribution and wheels into .var/dist directory
build:
	@echo "Building distribution packages..."
	uv build --out-dir $(OUTPUT_DIR)

# Run script
run:
	$(PYTHON) ./src/gflx/clickhouse/macro/__main__.py $(ARGS)

release-patch:
	$(BUMPVER) update --patch

release-minor:
	$(BUMPVER) update --minor

release-major:
	$(BUMPVER) update --major

# Remove virtual environment, lockfiles, cache, and build artifacts
clean:
	@echo "Cleaning up project workspace..."
	-$(RMDIR) $(VENV)
	-$(RMDIR) $(VAR_DIR)
	-$(RM) uv.lock
	-$(RM) .coverage
	$(CLEAR_DEEP_CACHE)
