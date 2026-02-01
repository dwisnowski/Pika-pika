# Find uv executable
UV_CANDIDATE := $(shell where uv 2>NUL || which uv 2>/dev/null)
ifeq ($(UV_CANDIDATE),)
  # Fallback for this machine if not in PATH
  UV := C:/Users/xtr3m/.local/bin/uv.exe
else
  UV := uv
endif

.PHONY: help setup sync fresh-install run dev diagnose check-running docs docs-sync docs-serve icons clean stop stop-restart verify verify-full
# Default target
help:
	@echo "Pika-pika Makefile"
	@echo ""
	@echo "Production (Raspberry Pi) targets:"
	@echo "  make setup          - Run initial setup script (installs system packages, creates venv, installs deps)"
	@echo "  make sync           - Sync dependencies and install package using uv (creates venv if needed)"
	@echo "  make doctor         - Scan for I2C/SPI hardware and check interface status"
	@echo "  make run            - Run the app in production mode (single worker for low-powered devices)"
	@echo "                      - Prevents starting if another instance is already running on port 8000"
	@echo ""
	@echo "Development targets:"
	@echo "  make dev            - Run the app in development mode with auto-reload"
	@echo "                      - Prevents starting if another instance is already running on port 8000"
	@echo "  make verify         - Quick health check of core infrastructure (30 seconds)"
	@echo "  make verify-full    - Comprehensive validation including property-based tests (5+ minutes)"
	@echo "  make stop-restart   - Stop any running pika-pika app and restart it"
	@echo "  make docs           - Build MkDocs documentation site (syncs docs dependencies)"
	@echo "  make docs-serve     - Serve docs locally for development (syncs docs dependencies)"
	@echo "  make icons          - Generate favicons and optimized image assets from PNG"
	@echo "  make clean          - Remove virtual environment and build artifacts"
	@echo ""
	@echo "Quick start (production):"
	@echo "  make setup          # Complete setup on Raspberry Pi"
	@echo "  make run            # Start the application"
	@echo ""
	@echo "Quick start (development):"
	@echo "  make sync           # Sync dependencies and install package"
	@echo "  make verify         # Quick health check (recommended before development)"
	@echo "  make dev            # Run with auto-reload"
	@echo "  make stop-restart   # Stop and restart the app"
	@echo "  make stop           # Stop any running pika-pika app"
	@echo ""
	@echo "Useful for development when you want to ensure a clean restart"
	@echo ""

# ============================================================================
# Production targets (for Raspberry Pi)
# ============================================================================

# Check if app is already running on port 8000
check-running:
	$(UV) run python scripts/check_app_running.py

# Run initial setup script on Raspberry Pi
setup:
	@bash scripts/setup_pi.sh

# Scan for I2C and SPI hardware
doctor:
	@chmod +x scripts/doctor.sh 2>/dev/null || true
	@bash scripts/doctor.sh

# Sync dependencies and install of package (creates venv if needed)
sync:
	$(UV) sync

# Run the app in production mode (single worker for low-powered devices)
run: check-running
	@if [ -f "/proc/device-tree/model" ] && grep -q "Raspberry Pi" /proc/device-tree/model 2>/dev/null; then \
		echo "[pika-pika] Detected Raspberry Pi, installing rpi extras..."; \
		$(UV) sync --extra rpi || echo "[pika-pika] Warning: rpi extras could not be installed"; \
	fi
	$(UV) run uvicorn pika.app:app --host 0.0.0.0 --port 8000 --workers 1

# ============================================================================
# Development targets
# ============================================================================
# Run the app in development mode with auto-reload
dev: sync check-running
	$(UV) run uvicorn pika.app:app --reload --host 0.0.0.0 --port 8000

# Quick health check of core infrastructure (30 seconds)
verify: sync
	@echo "Running quick verification of core infrastructure..."
	$(UV) run python scripts/quick_verification.py

# Comprehensive validation including property-based tests (5+ minutes)
verify-full: sync
	@echo "Running comprehensive infrastructure verification..."
	$(UV) run python scripts/verify_core_infrastructure.py

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

# Stop and restart target
stop-restart:
	@echo "Stopping any running pika-pika processes..."
	@$(UV) run python scripts/check_app_running.py
	@if errorlevel 1 (
		echo "pika-pika application is already running"
		exit /b 1
	) else (
		echo "No pika-pika application found running"
	)
	@echo "Waiting 2 seconds for processes to fully stop..."
	@timeout /t 2 >nul 2>&1 || echo "Timeout command not available, continuing..."
	@echo "Restarting pika-pika application..."
	@$(MAKE) dev

# Stop target
stop:
	@echo "Stopping any running pika-pika processes..."
	@$(UV) run python scripts/check_app_running.py && echo "No pika-pika application found running" || echo "pika-pika application is already running"
	@echo "Waiting 2 seconds for processes to fully stop..."
	@timeout /t 2 >nul 2>&1 || echo "Timeout command not available, continuing..."
	@echo "Stopping pika-pika application..."
	@taskkill /F /IM uvicorn.exe 2>NUL || echo "No uvicorn processes found"
