# Find uv executable
UV_CANDIDATE := $(shell where uv 2>NUL || which uv 2>/dev/null)
ifeq ($(UV_CANDIDATE),)
  # Fallback for this machine if not in PATH
  UV := C:/Users/xtr3m/.local/bin/uv.exe
else
  UV := uv
endif

.PHONY: help setup sync fresh-install run dev diagnose check-running docs docs-sync docs-serve icons clean stop stop-restart
# Default target
help:
	@echo "Pika-pika Makefile"
	@echo ""
	@echo "  make docs           - Build MkDocs documentation site (syncs docs dependencies)"
	@echo "  make docs-serve     - Serve docs locally for development (syncs docs dependencies)"
	@echo ""

# Sync dependencies and install of package (creates venv if needed)
sync:
	$(UV) sync

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
