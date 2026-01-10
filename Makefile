VENV := .venv
PY := $(VENV)/bin/python
UV := uv
UVICORN := $(VENV)/bin/uvicorn

.PHONY: help setup venv install run dev clean

help:
	@echo "Targets: setup, venv, install, run, dev, icons, clean"

icons:
	python scripts/generate_icons.py

# Build the MkDocs site locally (requires mkdocs or use `uv pip install .[docs]`)
docs: venv docs-sync
	$(UV) pip install mkdocs mkdocs-material
	$(VENV)/bin/mkdocs build

# Sync README into docs before building
docs-sync:
	$(PY) scripts/sync_readme_to_docs.py

# Serve the docs locally for development
docs-serve: venv
	$(UV) pip install mkdocs mkdocs-material
	$(VENV)/bin/mkdocs serve

setup:
	@bash scripts/setup_pi.sh

venv:
	python3 -m venv $(VENV)
	$(UV) pip install --upgrade pip setuptools wheel

install: venv
	$(UV) pip install .

run:
	# Single worker is recommended for low-powered devices
	$(UVICORN) pika.app:app --host 0.0.0.0 --port 8000 --workers 1

dev:
	$(UVICORN) pika.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf $(VENV) build dist *.egg-info
