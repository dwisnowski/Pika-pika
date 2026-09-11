CC = gcc
CFLAGS = -Wall -O2 -D_FILE_OFFSET_BITS=64 -I./include -I../pru/include -pthread
LDFLAGS = -pthread -lyaml -lm -lrt

SRC_DIR = src
OBJ_DIR = obj
BIN_DIR = bin

SRCS = $(wildcard $(SRC_DIR)/*.c) main.c
OBJS = $(patsubst $(SRC_DIR)/%.c,$(OBJ_DIR)/%.o,$(filter $(SRC_DIR)/%.c,$(SRCS)))
OBJS += $(OBJ_DIR)/main.o

TARGET = $(BIN_DIR)/datalogger

all: $(TARGET)

$(TARGET): $(OBJS)
	@mkdir -p $(BIN_DIR)
	$(CC) $(OBJS) -o $@ $(LDFLAGS)

$(OBJ_DIR)/%.o: $(SRC_DIR)/%.c
	@mkdir -p $(OBJ_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(OBJ_DIR)/main.o: main.c
	@mkdir -p $(OBJ_DIR)
	$(CC) $(CFLAGS) -c $< -o $@

# Header edits must rebuild consumers (decimator_t layout, etc.)
$(OBJ_DIR)/decimator.o: include/decimator.h
$(OBJ_DIR)/main.o: include/decimator.h include/vrms_rollup.h include/storage_format.h
$(OBJ_DIR)/vrms_rollup.o: include/vrms_rollup.h
$(OBJ_DIR)/anomaly_detector.o: include/anomaly_detector.h include/storage_format.h
$(OBJ_DIR)/event_window.o: include/event_window.h include/storage_format.h
$(OBJ_DIR)/writer.o: include/writer.h include/storage_format.h

clean-compiled:
	@sudo rm -rf $(OBJ_DIR) $(BIN_DIR)

clean-data:
	@sudo rm -f data/*.bin data/*.old data/*.jsonl data/write_probe.txt data/calibration_status.txt

clean: clean-compiled clean-data

run: all
	@sudo ./$(TARGET)

validate:
	python3 validate_data.py

test-time-utils:
	gcc -Wall -O2 -I./include test_time_utils.c src/time_utils.c -o test_time_utils -lrt
	./test_time_utils

validate-verbose:
	python3 validate_data.py --verbose

validate-diagnose:
	sudo python3 validate_data.py --verbose --diagnose

.PHONY: all clean clean-data clean-all run validate validate-verbose validate-diagnose test-time-utils
