# Data Logger Makefile
# Builds the Linux userspace datalogger that reads ADC data from the PRU.
# Requires: PRU firmware installed first (from top level: make pru-load).

CC ?= gcc
CFLAGS := -Wall -Wextra -I../pru/include
TARGET := datalogger

.PHONY: all build clean run

all: build
build: $(TARGET)

$(TARGET): main.c
	$(CC) $(CFLAGS) -o $@ $<

clean:
	rm -f $(TARGET)

# Run the datalogger (PRU firmware must already be in /lib/firmware; run make pru-load once from top level)
run: build
	@sudo ./$(TARGET)
