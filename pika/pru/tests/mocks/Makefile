# Makefile for PRU Mock Libraries
# Builds mock implementations of PRU hardware for host testing

CC = gcc
CFLAGS = -Wall -Wextra -std=c99 -fPIC
AR = ar

# Output library
MOCK_LIB = libpru_mocks.a

# Source files
SOURCES = pru_registers.c cycle_counter.c

# Object files
OBJECTS = $(SOURCES:.c=.o)

# Default target: build mock library
all: $(MOCK_LIB)

# Build static library
$(MOCK_LIB): $(OBJECTS)
	$(AR) rcs $@ $^

# Compile object files
%.o: %.c %.h
	$(CC) $(CFLAGS) -c $< -o $@

# Clean build artifacts
clean:
	rm -f $(OBJECTS) $(MOCK_LIB)

.PHONY: all clean
