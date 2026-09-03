# Root wrapper Makefile
#
# Delegates all targets to pika/Makefile so commands can be run from
# the repository root.

SUBPROJECT_DIR := pika

.PHONY: all pru datalogger web clean test-pru pru-bringup pru-load pru-load-bringup pru-stop pru-overlay run-datalogger run-all stop help setup run-pru-datalogger web-setup run-web startscreen

all pru datalogger web clean test-pru pru-bringup pru-load pru-load-bringup pru-stop pru-overlay run-datalogger run-all stop help setup run-pru-datalogger web-setup run-web startscreen:
	$(MAKE) -C $(SUBPROJECT_DIR) $@

# Forward any other target to the subproject Makefile.
%:
	$(MAKE) -C $(SUBPROJECT_DIR) $@
