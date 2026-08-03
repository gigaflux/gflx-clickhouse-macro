# Configuration
VENV = .venv
# For Linux / macOS:
PYTHON = $(VENV)/bin/python
# For Windows (native cmd/powershell), uncomment the line below:
# PYTHON = $(VENV)/Scripts/python.exe
OUTPUT_DIR = var/dist

.PHONY: all sync test lint format check trivy-scan build check-dist clean

# Default target
all: sync

# Sync environment using a hidden marker file to avoid loop updates on the directory timestamp
sync: $(VENV)/.uv-sync

$(VENV)/.uv-sync: pyproject.toml
	@echo "Syncing environment and installing dev dependencies..."
	uv sync
	@touch $(VENV)/.uv-sync

# --- Development Tools (dev group) ---

# Run tests with coverage based on pytest.ini settings
test-unit: sync
	@mkdir -p var
	$(VENV)/bin/pytest tests/unit

test-integration: sync
	$(VENV)/bin/pytest tests/integration --no-cov

# Run code linters, type checkers, and spell checkers (optimized for Namespace packages)
lint: sync
	$(VENV)/bin/ruff check
	$(VENV)/bin/codespell
	$(VENV)/bin/ty check

# Auto-format Python code and Markdown files (with GFM plugin support)
format: sync
	$(VENV)/bin/ruff format
	$(VENV)/bin/mdformat --wrap no --plugin gfm README.md

# Run security vulnerability scan using Trivy
scan: sync
	@echo "Running vulnerability and secret scanning with Trivy Docker container..."
	mkdir -p $(HOME)/.cache/trivy
	docker run --rm \
		-v $(PWD):/apps \
		-v $(HOME)/.cache/trivy:/root/.cache/trivy \
		aquasec/trivy:latest fs --scanners vuln,secret --severity CRITICAL,HIGH --ignore-unfixed /apps

# Run all pre-commit checks (linting + testing + security scan)
check: lint test-unit test-integration scan

# --- Build & Release Tools ---

# Build source distribution and wheels into dist/ directory
build: sync
	@echo "Building distribution packages..."
	rm -rf $(OUTPUT_DIR)
	mkdir -p $(OUTPUT_DIR)
	$(PYTHON) -m build --outdir $(OUTPUT_DIR)
	@echo "Checking built artifacts with twine..."
	$(VENV)/bin/twine check $(OUTPUT_DIR)/*

# Remove virtual environment, lockfiles, cache, and build artifacts
clean:
	rm -rf $(VENV)
	rm -f uv.lock
	rm -rf var/ .pytest_cache/ .coverage .ruff_cache/
