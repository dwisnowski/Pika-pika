CC = gcc
CFLAGS = -Wall -O2 -I./include -I../pru/include -pthread
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

clean-compiled:
	@sudo rm -rf $(OBJ_DIR) $(BIN_DIR)

clean-data:
	@sudo rm -f data/*.bin data/*.old

clean: clean-compiled clean-data

run: all
	@sudo ./$(TARGET)

validate:
	python3 validate_data.py

validate-verbose:
	python3 validate_data.py --verbose

validate-diagnose:
	sudo python3 validate_data.py --verbose --diagnose

.PHONY: all clean clean-data clean-all run validate validate-verbose validate-diagnose
