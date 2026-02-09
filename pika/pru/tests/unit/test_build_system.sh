#!/bin/bash
# Unit tests for PRU firmware build system
# Tests Requirements: 9.1, 9.2, 9.4, 9.5

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Get script directory and PRU root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRU_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=========================================="
echo "PRU Build System Unit Tests"
echo "=========================================="
echo "PRU Root: $PRU_ROOT"
echo ""

# Helper function to run a test
run_test() {
    local test_name="$1"
    local test_func="$2"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test $TESTS_RUN: $test_name ... "
    
    if $test_func; then
        echo -e "${GREEN}PASS${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}FAIL${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Helper function to check if file exists
file_exists() {
    local file="$1"
    if [ -f "$file" ]; then
        return 0
    else
        echo -e "\n  ${RED}Error: File not found: $file${NC}"
        return 1
    fi
}

# Helper function to check if directory exists
dir_exists() {
    local dir="$1"
    if [ -d "$dir" ]; then
        return 0
    else
        echo -e "\n  ${RED}Error: Directory not found: $dir${NC}"
        return 1
    fi
}

# =============================================================================
# Test Functions
# =============================================================================

# Test 1: Verify Makefile exists
test_makefile_exists() {
    file_exists "$PRU_ROOT/Makefile"
}

# Test 2: Verify firmware directory exists or can be created
test_firmware_directory() {
    # The firmware directory should exist or be created by make
    if [ -d "$PRU_ROOT/firmware" ]; then
        return 0
    else
        # Try to create it (make should do this)
        mkdir -p "$PRU_ROOT/firmware" 2>/dev/null
        return $?
    fi
}

# Test 3: Verify source files exist
test_source_files_exist() {
    file_exists "$PRU_ROOT/src/pru_main.c" && \
    file_exists "$PRU_ROOT/src/pru_bringup.c" && \
    file_exists "$PRU_ROOT/src/timing.c" && \
    file_exists "$PRU_ROOT/src/adc_parallel.c"
}

# Test 4: Verify header files exist
test_header_files_exist() {
    file_exists "$PRU_ROOT/include/shm_layout.h" && \
    file_exists "$PRU_ROOT/include/pru_config.h" && \
    file_exists "$PRU_ROOT/include/timing.h" && \
    file_exists "$PRU_ROOT/include/adc_parallel.h"
}

# Test 5: Verify Makefile has required targets
test_makefile_targets() {
    local makefile="$PRU_ROOT/Makefile"
    
    # Check for required targets
    if ! grep -q "^build:" "$makefile"; then
        echo -e "\n  ${RED}Error: 'build' target not found${NC}"
        return 1
    fi
    
    if ! grep -q "^bringup:" "$makefile"; then
        echo -e "\n  ${RED}Error: 'bringup' target not found${NC}"
        return 1
    fi
    
    if ! grep -q "^load:" "$makefile"; then
        echo -e "\n  ${RED}Error: 'load' target not found${NC}"
        return 1
    fi
    
    if ! grep -q "^clean:" "$makefile"; then
        echo -e "\n  ${RED}Error: 'clean' target not found${NC}"
        return 1
    fi
    
    return 0
}

# Test 6: Verify Makefile uses TI PRU compiler (Requirement 9.6)
test_makefile_uses_pru_compiler() {
    local makefile="$PRU_ROOT/Makefile"
    
    if ! grep -q "clpru" "$makefile"; then
        echo -e "\n  ${RED}Error: TI PRU compiler (clpru) not found in Makefile${NC}"
        return 1
    fi
    
    return 0
}

# Test 7: Verify Makefile has optimization flags (Requirement 9.6)
test_makefile_optimization_flags() {
    local makefile="$PRU_ROOT/Makefile"
    
    if ! grep -q "\-O2" "$makefile"; then
        echo -e "\n  ${RED}Error: -O2 optimization flag not found${NC}"
        return 1
    fi
    
    return 0
}

# Test 8: Verify Makefile outputs to firmware/ directory (Requirement 9.5)
test_makefile_firmware_output() {
    local makefile="$PRU_ROOT/Makefile"
    
    # Check for ad7606_sampler.out (may use variables)
    if ! grep -q "ad7606_sampler\.out" "$makefile"; then
        echo -e "\n  ${RED}Error: Main firmware output (ad7606_sampler.out) not found${NC}"
        return 1
    fi
    
    # Check for bringup_test.out (may use variables)
    if ! grep -q "bringup_test\.out" "$makefile"; then
        echo -e "\n  ${RED}Error: Bringup firmware output (bringup_test.out) not found${NC}"
        return 1
    fi
    
    # Check that firmware directory is used
    if ! grep -q "FIRMWARE_DIR" "$makefile" && ! grep -q "firmware/" "$makefile"; then
        echo -e "\n  ${RED}Error: Firmware directory not configured${NC}"
        return 1
    fi
    
    return 0
}

# Test 9: Test clean target behavior (Requirement 9.4)
test_clean_target() {
    cd "$PRU_ROOT"
    
    # Create dummy build artifacts
    mkdir -p build firmware
    touch build/dummy.obj
    touch firmware/dummy.out
    
    # Run clean (should not fail even if compiler not installed)
    if make clean >/dev/null 2>&1; then
        # Verify artifacts are removed
        if [ -f "build/dummy.obj" ] || [ -f "firmware/dummy.out" ]; then
            echo -e "\n  ${RED}Error: Clean target did not remove artifacts${NC}"
            return 1
        fi
        return 0
    else
        echo -e "\n  ${RED}Error: Clean target failed${NC}"
        return 1
    fi
}

# Test 10: Verify build directory structure
test_build_directory_structure() {
    # Check that required directories exist or can be created
    mkdir -p "$PRU_ROOT/build" "$PRU_ROOT/firmware" 2>/dev/null
    
    dir_exists "$PRU_ROOT/src" && \
    dir_exists "$PRU_ROOT/include"
}

# Test 11: Check for help target
test_help_target() {
    local makefile="$PRU_ROOT/Makefile"
    
    if ! grep -q "^help:" "$makefile"; then
        echo -e "\n  ${YELLOW}Warning: 'help' target not found (optional)${NC}"
        # This is not a failure, just a warning
    fi
    
    return 0
}

# Test 12: Verify Makefile syntax (basic check)
test_makefile_syntax() {
    cd "$PRU_ROOT"
    
    # Try to parse the Makefile (this will fail if syntax is bad)
    if make -n help >/dev/null 2>&1 || make -n clean >/dev/null 2>&1; then
        return 0
    else
        echo -e "\n  ${RED}Error: Makefile has syntax errors${NC}"
        return 1
    fi
}

# =============================================================================
# Conditional Tests (only if PRU compiler is available)
# =============================================================================

# Check if PRU compiler is available
check_pru_compiler() {
    if command -v clpru >/dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

# Test 13: Build main firmware (Requirement 9.1) - only if compiler available
test_build_main_firmware() {
    if ! check_pru_compiler; then
        echo -e "\n  ${YELLOW}Skipped: PRU compiler not available${NC}"
        return 0  # Not a failure, just skipped
    fi
    
    cd "$PRU_ROOT"
    
    # Clean first
    make clean >/dev/null 2>&1
    
    # Try to build
    if make build 2>&1 | tee /tmp/pru_build.log; then
        # Check if output file was created
        if file_exists "$PRU_ROOT/firmware/ad7606_sampler.out"; then
            return 0
        else
            echo -e "\n  ${RED}Error: Build succeeded but output file not found${NC}"
            return 1
        fi
    else
        echo -e "\n  ${RED}Error: Build failed${NC}"
        cat /tmp/pru_build.log
        return 1
    fi
}

# Test 14: Build bringup firmware (Requirement 9.2) - only if compiler available
test_build_bringup_firmware() {
    if ! check_pru_compiler; then
        echo -e "\n  ${YELLOW}Skipped: PRU compiler not available${NC}"
        return 0  # Not a failure, just skipped
    fi
    
    cd "$PRU_ROOT"
    
    # Clean first
    make clean >/dev/null 2>&1
    
    # Try to build
    if make bringup 2>&1 | tee /tmp/pru_bringup.log; then
        # Check if output file was created
        if file_exists "$PRU_ROOT/firmware/bringup_test.out"; then
            return 0
        else
            echo -e "\n  ${RED}Error: Build succeeded but output file not found${NC}"
            return 1
        fi
    else
        echo -e "\n  ${RED}Error: Build failed${NC}"
        cat /tmp/pru_bringup.log
        return 1
    fi
}

# =============================================================================
# Run All Tests
# =============================================================================

echo "Running build system tests..."
echo ""

# Basic structure tests (always run)
run_test "Makefile exists" test_makefile_exists
run_test "Firmware directory exists or can be created" test_firmware_directory
run_test "Source files exist" test_source_files_exist
run_test "Header files exist" test_header_files_exist
run_test "Makefile has required targets" test_makefile_targets
run_test "Makefile uses TI PRU compiler" test_makefile_uses_pru_compiler
run_test "Makefile has optimization flags" test_makefile_optimization_flags
run_test "Makefile outputs to firmware/ directory" test_makefile_firmware_output
run_test "Clean target works" test_clean_target
run_test "Build directory structure" test_build_directory_structure
run_test "Help target exists" test_help_target
run_test "Makefile syntax is valid" test_makefile_syntax

# Compilation tests (only if compiler available)
if check_pru_compiler; then
    echo ""
    echo "PRU compiler detected - running compilation tests..."
    echo ""
    run_test "Build main firmware (Requirement 9.1)" test_build_main_firmware
    run_test "Build bringup firmware (Requirement 9.2)" test_build_bringup_firmware
else
    echo ""
    echo -e "${YELLOW}PRU compiler not detected - skipping compilation tests${NC}"
    echo "Install TI PRU compiler to run full tests"
    echo ""
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo "Tests run:    $TESTS_RUN"
echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
if [ $TESTS_FAILED -gt 0 ]; then
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
else
    echo -e "Tests failed: $TESTS_FAILED"
fi
echo "=========================================="

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
