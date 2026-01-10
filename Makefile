VENV := .venv
PY := $(VENV)/bin/python
UV := uv
UVICORN := $(VENV)/bin/uvicorn

.PHONY: help setup venv install run dev docs docs-sync docs-serve icons clean

# Default target
help:
	@echo "Pika-pika Makefile"
	@echo ""
	@echo "Production (Raspberry Pi) targets:"
	@echo "  make setup          - Run initial setup script (installs system packages, creates venv, installs deps)"
	@echo "  make venv           - Create Python virtual environment (.venv)"
	@echo "  make install        - Install the package and dependencies (requires venv)"
	@echo "  make run            - Run the app in production mode (single worker for low-powered devices)"
	@echo ""
	@echo "Development targets:"
	@echo "  make dev            - Run the app in development mode with auto-reload"
	@echo "  make docs           - Build MkDocs documentation site (requires venv)"
	@echo "  make docs-serve     - Serve docs locally for development (requires venv)"
	@echo "  make docs-sync      - Sync README.md into docs before building"
	@echo "  make icons          - Generate favicons and optimized image assets from PNG"
	@echo "  make clean          - Remove virtual environment and build artifacts"
	@echo ""
	@echo "Quick start (production):"
	@echo "  make setup          # Complete setup on Raspberry Pi"
	@echo "  make run            # Start the application"
	@echo ""
	@echo "Quick start (development):"
	@echo "  make venv           # Create virtual environment"
	@echo "  make install        # Install dependencies"
	@echo "  make dev            # Run with auto-reload"

# ============================================================================
# Production targets (for Raspberry Pi)
# ============================================================================

# Run initial setup script on Raspberry Pi
setup:
	@bash scripts/setup_pi.sh

# Create Python virtual environment
venv:
	python3 -m venv $(VENV)
	$(UV) pip install --upgrade pip setuptools wheel

# Install the package and dependencies (requires venv)
install: venv
	$(UV) pip install .

# Run the app in production mode (single worker for low-powered devices)
run:
	$(UVICORN) pika.app:app --host 0.0.0.0 --port 8000 --workers 1

# ============================================================================
# Development targets
# ============================================================================

# Run the app in development mode with auto-reload
dev:
	$(UVICORN) pika.app:app --reload --host 0.0.0.0 --port 8000

# Build the MkDocs documentation site
docs: venv docs-sync
	$(UV) pip install mkdocs mkdocs-material
	$(VENV)/bin/mkdocs build

# Sync README.md into docs before building
docs-sync:
	$(PY) scripts/sync_readme_to_docs.py

# Serve the docs locally for development
docs-serve: venv
	$(UV) pip install mkdocs mkdocs-material
	$(VENV)/bin/mkdocs serve

# Generate favicons and optimized image assets
icons:
	python scripts/generate_icons.py

# Clean up virtual environment and build artifacts
clean:
	rm -rf $(VENV) build dist *.egg-info
