# BeagleBone Black Data Acquisition System - Top-Level Makefile
#
# This Makefile orchestrates builds across all subprojects using a delegation pattern.
# Each target delegates to the corresponding subproject Makefile using $(MAKE) -C.
#
# Targets:
#   all        - Build all components (PRU firmware, data logger, web application)
#   pru        - Build PRU firmware only
#   datalogger - Build data logger only
#   web        - Build web application only
#   clean      - Clean all build artifacts from all subprojects
#
# Delegation Pattern:
#   $(MAKE) -C <directory> invokes Make in the specified subdirectory,
#   executing the Makefile in that directory. This allows each component
#   to maintain its own build logic while providing a unified interface
#   at the top level.

.PHONY: all pru datalogger web clean test-pru pru-bringup pru-load pru-load-bringup pru-stop pru-overlay run-datalogger run-all stop help setup run-pru-datalogger daemon-install daemon-status daemon-stop daemon-uninstall daemon-enable daemon-disable startscreen shutdown clean-data tunnel-install tunnel-status tunnel-logs tunnel-uninstall

# Build all components
all: pru datalogger web

# Install system dependencies
setup:
	@echo "Installing system dependencies..."
	@sudo apt-get update && sudo apt-get install -y libyaml-dev

# Build PRU firmware - delegates to pru/Makefile
pru:
	$(MAKE) -C pru load

# Build PRU bringup firmware
pru-bringup:
	$(MAKE) -C pru bringup

# Build data logger - delegates to datalogger/Makefile
datalogger:
	$(MAKE) -C datalogger

# Build web application - delegates to webapp/Makefile
web:
	$(MAKE) -C webapp

# Test PRU firmware (unit + property tests)
test-pru:
	$(MAKE) -C pru test

# Load PRU firmware to BeagleBone Black
pru-load:
	$(MAKE) -C pru load

# Load PRU bringup firmware to BeagleBone Black
pru-load-bringup:
	$(MAKE) -C pru load-bringup

# Stop PRU
pru-stop:
	$(MAKE) -C pru stop

# Build and install device tree overlay
pru-overlay:
	$(MAKE) -C pru overlay install-overlay

# Web Application
web-setup:
	$(MAKE) -C webapp setup

run-web:
	$(MAKE) -C webapp run

# Run datalogger (builds first). PRU firmware must be installed: run make pru-load once.
run-datalogger: datalogger
	@sudo $(MAKE) -C datalogger run

# Build PRU firmware and datalogger, then run both.
run-pru-datalogger: pru datalogger
	@echo "Starting Datalogger (C)..."
	@sudo $(MAKE) -C datalogger run

# Build PRU firmware and datalogger, then run both.
run-all: pru datalogger web
	@echo "Starting Datalogger (C)..."
	@sudo $(MAKE) -C datalogger run &
	@echo "Starting Web Application (FastAPI)..."
	@$(MAKE) -C webapp run

stop:
	@echo "Stopping all Pika components..."
	-@sudo pkill -9 -f datalogger
	-@sudo pkill -9 -f uvicorn
	-@$(MAKE) -C pru stop
	@echo "Stopped."

# Systemd daemon management targets
daemon-install:
	@echo "Checking pika-run-all systemd service..."
	@if sudo systemctl list-unit-files pika-run-all.service 2>/dev/null | grep -q pika-run-all; then \
		echo "✓ Service already installed."; \
		echo "  To reinstall: make daemon-uninstall && make daemon-install"; \
		make daemon-status; \
	else \
		echo "Installing pika-run-all systemd service..."; \
		sudo cp ../etc/systemd/system/pika-run-all.service /etc/systemd/system/; \
		sudo systemctl daemon-reload; \
		sudo systemctl enable pika-run-all.service; \
		echo "✓ Service installed and enabled at boot."; \
		echo "  To start now: make daemon-start"; \
		echo "  To check status: make daemon-status"; \
	fi

daemon-enable:
	@echo "Enabling pika-run-all service at boot..."
	@sudo systemctl enable pika-run-all.service
	@echo "Service enabled."

daemon-disable:
	@echo "Disabling pika-run-all service at boot..."
	@sudo systemctl disable pika-run-all.service
	@echo "Service disabled."

daemon-status:
	@python3 scripts/pika_status.py

daemon-start:
	@echo "Starting pika-run-all service..."
	@sudo systemctl start pika-run-all.service
	@echo "Service started."

daemon-stop:
	@echo "Stopping pika-run-all service..."
	@sudo systemctl stop pika-run-all.service
	@echo "Service stopped."

daemon-restart:
	@echo "Restarting pika-run-all service..."
	@sudo systemctl restart pika-run-all.service
	@echo "Service restarted."

daemon-logs:
	@echo "Displaying pika-run-all service logs..."
	@sudo journalctl -u pika-run-all.service -n 100 --no-pager -f

daemon-uninstall:
	@echo "Uninstalling pika-run-all systemd service..."
	@sudo systemctl disable pika-run-all.service || true
	@sudo systemctl stop pika-run-all.service || true
	@sudo rm -f /etc/systemd/system/pika-run-all.service
	@sudo systemctl daemon-reload
	@echo "Service uninstalled."

# Cloudflare Tunnel (pika.wildideazone.com). Token comes from ../.cloudflared.env
# (gitignored — copy it to the BBB, never commit it).
TUNNEL_ENV := ../.cloudflared.env
TUNNEL_TOKEN_FILE := /etc/cloudflared/pika.env

tunnel-install:
	@test -f $(TUNNEL_ENV) || { echo "error: missing $(TUNNEL_ENV) (TUNNEL_TOKEN=...)"; exit 1; }
	@grep -q '^TUNNEL_TOKEN=.' $(TUNNEL_ENV) || { echo "error: TUNNEL_TOKEN not set in $(TUNNEL_ENV)"; exit 1; }
	@if ! command -v cloudflared >/dev/null 2>&1; then \
		echo "Adding Cloudflare apt repository + installing cloudflared..."; \
		sudo mkdir -p --mode=0755 /usr/share/keyrings; \
		curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null; \
		echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null; \
		sudo apt-get update && sudo apt-get install -y cloudflared; \
	fi
	@echo "Installing tunnel token → $(TUNNEL_TOKEN_FILE)..."
	@sudo install -d -m 700 /etc/cloudflared
	@sudo install -m 600 $(TUNNEL_ENV) $(TUNNEL_TOKEN_FILE)
	@sudo cp ../etc/systemd/system/pika-cloudflared.service /etc/systemd/system/
	@sudo systemctl daemon-reload
	@sudo systemctl enable --now pika-cloudflared.service
	@echo "✓ Tunnel installed and running: https://pika.wildideazone.com"

tunnel-status:
	@sudo systemctl --no-pager --full status pika-cloudflared.service

tunnel-logs:
	@sudo journalctl -u pika-cloudflared.service -n 100 --no-pager -f

tunnel-uninstall:
	@sudo systemctl disable --now pika-cloudflared.service || true
	@sudo rm -f /etc/systemd/system/pika-cloudflared.service $(TUNNEL_TOKEN_FILE)
	@sudo systemctl daemon-reload
	@echo "Tunnel uninstalled."

# Clean all build artifacts - delegates to all subproject Makefiles
clean:
	$(MAKE) -C pru clean
	$(MAKE) -C datalogger clean
# 	$(MAKE) -C webapp clean  #  Not needed most of the time. <-----

# Delete stored trend/event files. Stops the daemon first so open FDs
# do not keep the old inodes allocated; restarts it if it was running.
clean-data:
	@DATA_DIR="$(CURDIR)/datalogger/data"; \
	BEFORE=$$(du -sb "$$DATA_DIR" 2>/dev/null | awk '{print $$1}'); \
	[ -z "$$BEFORE" ] && BEFORE=0; \
	RESTART=0; \
	if command -v systemctl >/dev/null 2>&1 && \
	   systemctl is-active --quiet pika-run-all.service 2>/dev/null; then \
		echo "Stopping pika-run-all so stored files can be removed..."; \
		sudo systemctl stop pika-run-all.service; \
		RESTART=1; \
	fi; \
	$(MAKE) -C datalogger clean-data; \
	if [ "$$RESTART" = "1" ]; then \
		echo "Restarting pika-run-all..."; \
		sudo systemctl start pika-run-all.service; \
	fi; \
	AFTER=$$(du -sb "$$DATA_DIR" 2>/dev/null | awk '{print $$1}'); \
	[ -z "$$AFTER" ] && AFTER=0; \
	FREED=$$((BEFORE - AFTER)); \
	if [ "$$FREED" -lt 0 ]; then FREED=0; fi; \
	echo "Cleared Pika stored data ($$((FREED / 1024)) KB freed)."; \
	df -h / | awk 'NR==2{printf "Disk / is now %s used, %s available.\n", $$5, $$4}'

# Armbian-style start screen / MOTD (run on BBB)
startscreen:
	@echo ""
	@echo "  ____  _ _            "
	@echo " |  _ \(_) | ____ _   "
	@echo " | |_) | | |/ / _\` |  "
	@echo " |  __/| |   < (_| |  "
	@echo " |_|   |_|_|\_\__,_|  "
	@echo ""
	@HOSTNAME=$$(hostname 2>/dev/null || echo unknown); \
	KERNEL=$$(uname -r 2>/dev/null || echo unknown); \
	UPTIME=$$(uptime -p 2>/dev/null | sed 's/^up //'); \
	[ -z "$$UPTIME" ] && UPTIME=$$(awk '{printf "%d min", $$1/60}' /proc/uptime 2>/dev/null || echo unknown); \
	LOAD=$$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo "n/a"); \
	CPU_USAGE="n/a"; \
	if [ -r /proc/stat ]; then \
		CPU_IDLE1=$$(awk '/^cpu /{print $$5; exit}' /proc/stat); \
		CPU_TOTAL1=$$(awk '/^cpu /{print $$2+$$3+$$4+$$5+$$6+$$7+$$8; exit}' /proc/stat); \
		sleep 0.5; \
		CPU_IDLE2=$$(awk '/^cpu /{print $$5; exit}' /proc/stat); \
		CPU_TOTAL2=$$(awk '/^cpu /{print $$2+$$3+$$4+$$5+$$6+$$7+$$8; exit}' /proc/stat); \
		CPU_USAGE=$$(awk -v i1="$$CPU_IDLE1" -v t1="$$CPU_TOTAL1" -v i2="$$CPU_IDLE2" -v t2="$$CPU_TOTAL2" \
			'BEGIN { dt=t2-t1; di=i2-i1; if (dt>0) printf "%.1f%%", (1-di/dt)*100; else print "n/a" }'); \
	fi; \
	MEM=$$(free -m 2>/dev/null | awk '/^Mem:/{printf "%d%% of %dMB (%dMB used)", ($$3/$$2)*100, $$2, $$3}'); \
	DISK=$$(df -h / 2>/dev/null | awk 'NR==2{printf "%s of %s (%s used)", $$5, $$2, $$3}'); \
	IPS=$$(hostname -I 2>/dev/null | tr -s ' ' | sed 's/ *$$//'); \
	if [ -z "$$IPS" ]; then \
		IPS=$$(ip -4 -o addr show scope global 2>/dev/null | awk '{print $$4}' | cut -d/ -f1 | tr '\n' ' ' | sed 's/ *$$//'); \
	fi; \
	[ -z "$$IPS" ] && IPS="none"; \
	PRU0="n/a"; PRU1="n/a"; \
	if [ -f /sys/class/remoteproc/remoteproc1/state ]; then \
		PRU0=$$(cat /sys/class/remoteproc/remoteproc1/state 2>/dev/null); \
	fi; \
	if [ -f /sys/class/remoteproc/remoteproc2/state ]; then \
		PRU1=$$(cat /sys/class/remoteproc/remoteproc2/state 2>/dev/null); \
	fi; \
	PIKA_DIR="$$HOME/pika"; \
	if [ -d "$$PIKA_DIR" ]; then \
		PIKA_SIZE=$$(du -sh "$$PIKA_DIR" 2>/dev/null | cut -f1); \
	else \
		PIKA_SIZE="n/a (missing)"; \
	fi; \
	DATA_DIR="$(CURDIR)/datalogger/data"; \
	if [ -d "$$DATA_DIR" ]; then \
		DATA_SIZE=$$(du -sh "$$DATA_DIR" 2>/dev/null | cut -f1); \
	else \
		DATA_SIZE="n/a (no data yet)"; \
	fi; \
	printf " Welcome to \033[1mPika\033[0m on %s\n" "$$HOSTNAME"; \
	printf " Kernel: %s\n" "$$KERNEL"; \
	echo ""; \
	printf " System load:\t%s\tUp time:\t%s\n" "$$LOAD" "$$UPTIME"; \
	printf " CPU usage:\t%s\t\tMemory usage:\t%s\n" "$$CPU_USAGE" "$${MEM:-n/a}"; \
	printf " Usage of /:\t%s\n" "$${DISK:-n/a}"; \
	printf " IP address:\t%s\n" "$$IPS"; \
	printf " PRU0:\t\t%s\t\tPRU1:\t\t%s\n" "$$PRU0" "$$PRU1"; \
	printf " ~/pika:\t\t%s\t\tLogged data:\t%s\n" "$$PIKA_SIZE" "$$DATA_SIZE"; \
	echo ""

# Power off the BeagleBone (requires passwordless sudo for shutdown — see help)
shutdown:
	@echo "Shutting down..."
	@sudo shutdown -h now

# Help
help:
	@echo "Pika - BeagleBone Black Data Acquisition System"
	@echo "================================================"
	@echo ""
	@echo "Build Targets:"
	@echo "  all              - Build all components"
	@echo "  pru              - Build PRU firmware"
	@echo "  pru-bringup      - Build PRU bringup test firmware"
	@echo "  datalogger       - Build data logger"
	@echo "  web              - Build web application (planned)"
	@echo ""
	@echo "Run Targets:"
	@echo "  run-datalogger   - Build and run datalogger (run make pru-load once first)"
	@echo "  run-all          - Build pru + datalogger, then run datalogger"
	@echo "  stop             - Force stop all background components"
	@echo "  shutdown         - Power off the board (sudo shutdown -h now)"
	@echo ""
	@echo "Daemon/Systemd Targets (run on BBB):"
	@echo "  daemon-install   - Install pika-run-all service and enable at boot"
	@echo "  daemon-enable    - Enable service to start at boot"
	@echo "  daemon-disable   - Disable service from starting at boot"
	@echo "  daemon-start     - Start the service now"
	@echo "  daemon-stop      - Stop the service"
	@echo "  daemon-restart   - Restart the service"
	@echo "  daemon-status    - Show PRU / datalogger / web / host dashboard"
	@echo "  daemon-logs      - Follow service logs in real-time"
	@echo "  daemon-uninstall - Uninstall and remove the service"
	@echo ""
	@echo "Cloudflare Tunnel Targets (run on BBB; needs ../.cloudflared.env):"
	@echo "  tunnel-install   - Install cloudflared + pika-cloudflared service (pika.wildideazone.com)"
	@echo "  tunnel-status    - Show tunnel service status"
	@echo "  tunnel-logs      - Follow tunnel logs"
	@echo "  tunnel-uninstall - Remove the tunnel service and token"
	@echo ""
	@echo "PRU Targets:"
	@echo "  test-pru         - Run PRU firmware tests"
	@echo "  pru-load         - Load PRU firmware to BBB"
	@echo "  pru-load-bringup - Load PRU bringup firmware to BBB"
	@echo "  pru-stop         - Stop PRU"
	@echo "  pru-overlay      - Build and install device tree overlay"
	@echo ""
	@echo "Other:"
	@echo "  startscreen      - Print Armbian-style start screen (IP, CPU, mem, disk, PRUs, data size)"
	@echo "  setup            - Install system dependencies (libyaml-dev)"
	@echo "  clean            - Clean all build artifacts"
	@echo "  clean-data       - Stop daemon, delete stored trend/event files, restart"
	@echo "  help             - Show this help message"
	@echo ""
	@echo "See docs/getting-started.md for hardware setup instructions"
