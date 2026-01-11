UV := uv

.PHONY: help setup sync fresh-install run dev check-running docs docs-sync docs-serve icons clean

# Default target
help:
	@echo "Pika-pika Makefile"
	@echo ""
	@echo "Production (Raspberry Pi) targets:"
	@echo "  make setup          - Run initial setup script (installs system packages, creates venv, installs deps)"
	@echo "  make sync           - Sync dependencies and install package using uv (creates venv if needed)"
	@echo "  make run            - Run the app in production mode (single worker for low-powered devices)"
	@echo "                      - Prevents starting if another instance is already running on port 8000"
	@echo ""
	@echo "Development targets:"
	@echo "  make dev            - Run the app in development mode with auto-reload"
	@echo "                      - Prevents starting if another instance is already running on port 8000"
	@echo "  make docs           - Build MkDocs documentation site (syncs docs dependencies)"
	@echo "  make docs-serve     - Serve docs locally for development (syncs docs dependencies)"
	@echo "  make docs-sync      - Sync README.md into docs before building"
	@echo "  make icons          - Generate favicons and optimized image assets from PNG"
	@echo "  make clean          - Remove virtual environment and build artifacts"
	@echo ""
	@echo "Quick start (production):"
	@echo "  make setup          # Complete setup on Raspberry Pi"
	@echo "  make run            # Start the application"
	@echo ""
	@echo "Quick start (development):"
	@echo "  make sync           # Sync dependencies and install package"
	@echo "  make dev            # Run with auto-reload"

# ============================================================================
# Production targets (for Raspberry Pi)
# ============================================================================

# Check if app is already running on port 8000
check-running:
	@python scripts/check_port.py 8000

# Run initial setup script on Raspberry Pi
setup:
	@bash scripts/setup_pi.sh

# Sync dependencies and install the package (creates venv if needed)
sync:
	$(UV) sync

# Run the app in production mode (single worker for low-powered devices)
run: check-running
	$(UV) run uvicorn pika.app:app --host 0.0.0.0 --port 8000 --workers 1

# ============================================================================
# Development targets
# ============================================================================

# Run the app in development mode with auto-reload
dev: check-running
	$(UV) run uvicorn pika.app:app --reload --host 0.0.0.0 --port 8000

# Build the MkDocs documentation site
docs: docs-sync
	$(UV) sync --extra docs
	$(UV) run mkdocs build

# Sync README.md into docs before building
docs-sync:
	$(UV) run python scripts/sync_readme_to_docs.py

# Serve the docs locally for development
docs-serve:
	$(UV) sync --extra docs
	$(UV) run mkdocs serve

# Generate favicons and optimized image assets
icons:
	$(UV) run python scripts/generate_icons.py

# Clean up virtual environment and build artifacts
clean:
	rm -rf $(VENV) build dist *.egg-info
