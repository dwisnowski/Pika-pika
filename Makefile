VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn

.PHONY: help setup venv install run dev clean

help:
	@echo "Targets: setup, venv, install, run, dev, icons, clean"

icons:
	python scripts/generate_icons.py

setup:
	@bash scripts/setup_pi.sh

venv:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools wheel

install: venv
	$(PIP) install .

run:
	# Single worker is recommended for low-powered devices
	$(UVICORN) pika.app:app --host 0.0.0.0 --port 8000 --workers 1

dev:
	$(UVICORN) pika.app:app --reload --host 0.0.0.0 --port 8000

clean:
	rm -rf $(VENV) build dist *.egg-info
