# Robust UV path for sudo environments
UV := $(shell which uv 2>/dev/null || if [ -x /home/debian/.local/bin/uv ]; then echo /home/debian/.local/bin/uv; else echo uv; fi)

all:
	@echo "Webapp ready. Run 'make setup' if dependencies are missing."

setup:
	$(UV) sync

run:
	@echo "Starting webapp on port 8888 (Requires Sudo for SHM)..."
	sudo $(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8888

run-bg:
	@echo "Starting webapp in background..."
	sudo nohup $(UV) run uvicorn app.main:app --host 0.0.0.0 --port 8888 > webapp.log 2>&1 &

stop:
	@echo "Stopping webapp..."
	-sudo pkill -9 -f uvicorn

clean:
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} +
