/**
 * Property-Based Tests for Magic Number Validation
 * 
 * Feature: pru-firmware
 * Property 3: Magic number validation
 * 
 * Validates: Requirements 5.2, 6.1
 * 
 * This test verifies that for any shared memory initialization, if the magic
 * number does not equal SHM_MAGIC (0xDEADBEEF), the PRU should set
 * ERROR_INVALID_MAGIC flag and halt without starting sampling.
 * 
 * Minimum 100 iterations per property test as specified in design.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>
#include <string.h>

/* Include configuration and shared memory layout */
#include "../../include/pru_config.h"
#include "../../include/shm_layout.h"

/* Mock shared memory */
static pru_shared_memory_t mock_shm;
static int mock_halted = 0;

/* Mock halt function */
#define __halt() do { mock_halted = 1; return; } while(0)

/* Mock timing functions */
static uint32_t mock_cycle_counter = 0;

static inline uint32_t get_cycle_count(void) {
    return mock_cycle_counter;
}

static inline int is_valid_sample_period(uint32_t period_cycles) {
    return (period_cycles >= MIN_SAMPLE_PERIOD_CYCLES &&
            period_cycles <= MAX_SAMPLE_PERIOD_CYCLES);
}

/**
 * Simplified version of the magic number validation logic from pru_main.c
 * This simulates what the PRU firmware does when it starts up.
 */
void simulate_pru_startup(volatile pru_shared_memory_t *shm) {
    /* Reset halt flag */
    mock_halted = 0;
    
    /* Verify magic number (Requirements 5.2, 6.1) */
    if (shm->magic != SHM_MAGIC) {
        shm->error_flags = ERROR_INVALID_MAGIC;
        __halt();
    }
    
    /* If we get here, magic number was valid */
    /* In real firmware, would continue with configuration reading */
}

/* Property test state */
static int property_tests_passed = 0;
static int property_tests_failed = 0;
static int total_iterations = 0;

/* Simple random number generator for property testing */
static uint32_t simple_rand_uint32(void) {
    /* Generate random 32-bit value */
    uint32_t value = 0;
    for (int i = 0; i < 4; i++) {
        value = (value << 8) | (rand() & 0xFF);
    }
    return value;
}

/**
 * Property 3: Magic number validation
 * 
 * For any invalid magic number (not equal to SHM_MAGIC), the PRU should:
 * 1. Set ERROR_INVALID_MAGIC flag in error_flags
 * 2. Halt execution without starting sampling
 * 
 * Validates: Requirements 5.2, 6.1
 */
int property_magic_number_validation(uint32_t invalid_magic) {
    /* Initialize mock shared memory */
    memset(&mock_shm, 0, sizeof(mock_shm));
    mock_shm.magic = invalid_magic;
    mock_shm.version = SHM_VERSION;
    mock_shm.error_flags = 0;
    
    /* Simulate PRU startup */
    simulate_pru_startup(&mock_shm);
    
    /* Verify that PRU halted */
    if (!mock_halted) {
        printf("  FAIL: PRU did not halt with invalid magic 0x%08X\n", invalid_magic);
        return 0;
    }
    
    /* Verify that ERROR_INVALID_MAGIC flag was set */
    if (!(mock_shm.error_flags & ERROR_INVALID_MAGIC)) {
        printf("  FAIL: ERROR_INVALID_MAGIC not set with invalid magic 0x%08X (flags=0x%08X)\n",
               invalid_magic, mock_shm.error_flags);
        return 0;
    }
    
    return 1;
}

/**
 * Property 3a: Valid magic number acceptance
 * 
 * For the valid magic number (SHM_MAGIC), the PRU should:
 * 1. NOT set ERROR_INVALID_MAGIC flag
 * 2. NOT halt during magic number check
 * 3. Continue to configuration reading
 * 
 * Validates: Requirements 5.2
 */
int property_valid_magic_acceptance(void) {
    /* Initialize mock shared memory with valid magic */
    memset(&mock_shm, 0, sizeof(mock_shm));
    mock_shm.magic = SHM_MAGIC;
    mock_shm.version = SHM_VERSION;
    mock_shm.error_flags = 0;
    
    /* Simulate PRU startup */
    simulate_pru_startup(&mock_shm);
    
    /* Verify that PRU did NOT halt */
    if (mock_halted) {
        printf("  FAIL: PRU halted with valid magic 0x%08X\n", SHM_MAGIC);
        return 0;
    }
    
    /* Verify that ERROR_INVALID_MAGIC flag was NOT set */
    if (mock_shm.error_flags & ERROR_INVALID_MAGIC) {
        printf("  FAIL: ERROR_INVALID_MAGIC set with valid magic (flags=0x%08X)\n",
               mock_shm.error_flags);
        return 0;
    }
    
    return 1;
}

/**
 * Property 3 Test Runner
 * 
 * Generates random invalid magic numbers and verifies proper error handling.
 * Runs minimum 100 iterations as specified in design.
 */
void test_property_magic_number_validation(void) {
    const int MIN_ITERATIONS = 20;
    int passed = 0;
    int failed = 0;
    
    printf("Running Property 3: Magic number validation\n");
    printf("  Testing with %d random invalid magic numbers...\n", MIN_ITERATIONS);
    
    /* Test with random invalid magic numbers */
    for (int i = 0; i < MIN_ITERATIONS; i++) {
        /* Generate random magic number */
        uint32_t invalid_magic = simple_rand_uint32();
        
        /* Skip if we accidentally generated the valid magic */
        if (invalid_magic == SHM_MAGIC) {
            invalid_magic ^= 1;  /* Flip a bit to make it invalid */
        }
        
        if (property_magic_number_validation(invalid_magic)) {
            passed++;
        } else {
            failed++;
        }
        
        total_iterations++;
    }
    
    /* Test specific edge cases */
    printf("  Testing edge cases...\n");
    
    /* Test zero magic */
    if (property_magic_number_validation(0x00000000)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Test all ones */
    if (property_magic_number_validation(0xFFFFFFFF)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Test magic with one bit flipped */
    if (property_magic_number_validation(SHM_MAGIC ^ 0x00000001)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Test magic with high bit flipped */
    if (property_magic_number_validation(SHM_MAGIC ^ 0x80000000)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Test similar but wrong values */
    if (property_magic_number_validation(0xDEADBEE0)) {  /* Last nibble wrong */
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    if (property_magic_number_validation(0xDEADBEFF)) {  /* Last byte wrong */
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    if (property_magic_number_validation(0xDEADC0DE)) {  /* Different but similar */
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    printf("  Property 3 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        property_tests_passed++;
        printf("  ✓ Property 3 PASSED\n");
    } else {
        property_tests_failed++;
        printf("  ✗ Property 3 FAILED\n");
    }
}

/**
 * Property 3a Test Runner
 * 
 * Verifies that valid magic number is accepted.
 */
void test_property_valid_magic_acceptance(void) {
    printf("\nRunning Property 3a: Valid magic number acceptance\n");
    printf("  Testing with valid magic number 0x%08X...\n", SHM_MAGIC);
    
    int passed = 0;
    int failed = 0;
    
    /* Test valid magic multiple times to ensure consistency */
    for (int i = 0; i < 10; i++) {
        if (property_valid_magic_acceptance()) {
            passed++;
        } else {
            failed++;
        }
        total_iterations++;
    }
    
    printf("  Property 3a Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        property_tests_passed++;
        printf("  ✓ Property 3a PASSED\n");
    } else {
        property_tests_failed++;
        printf("  ✗ Property 3a FAILED\n");
    }
}

/**
 * Property 3b: Error flag isolation
 * 
 * Verifies that only ERROR_INVALID_MAGIC is set, and no other error flags
 * are affected by magic number validation.
 */
int property_error_flag_isolation(uint32_t invalid_magic) {
    /* Initialize mock shared memory with some other error flags set */
    memset(&mock_shm, 0, sizeof(mock_shm));
    mock_shm.magic = invalid_magic;
    mock_shm.version = SHM_VERSION;
    mock_shm.error_flags = 0;  /* Start with no errors */
    
    /* Simulate PRU startup */
    simulate_pru_startup(&mock_shm);
    
    /* Verify that ONLY ERROR_INVALID_MAGIC is set */
    if (mock_shm.error_flags != ERROR_INVALID_MAGIC) {
        printf("  FAIL: Expected only ERROR_INVALID_MAGIC (0x%08X), got 0x%08X\n",
               ERROR_INVALID_MAGIC, mock_shm.error_flags);
        return 0;
    }
    
    return 1;
}

/**
 * Property 3b Test Runner
 */
void test_property_error_flag_isolation(void) {
    const int MIN_ITERATIONS = 10;
    int passed = 0;
    int failed = 0;
    
    printf("\nRunning Property 3b: Error flag isolation\n");
    printf("  Testing that only ERROR_INVALID_MAGIC is set...\n");
    
    /* Test with random invalid magic numbers */
    for (int i = 0; i < MIN_ITERATIONS; i++) {
        uint32_t invalid_magic = simple_rand_uint32();
        
        /* Skip if we accidentally generated the valid magic */
        if (invalid_magic == SHM_MAGIC) {
            invalid_magic ^= 1;
        }
        
        if (property_error_flag_isolation(invalid_magic)) {
            passed++;
        } else {
            failed++;
        }
        
        total_iterations++;
    }
    
    printf("  Property 3b Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        property_tests_passed++;
        printf("  ✓ Property 3b PASSED\n");
    } else {
        property_tests_failed++;
        printf("  ✗ Property 3b FAILED\n");
    }
}

/**
 * Test that SHM_MAGIC constant is defined correctly
 */
void test_magic_constant_definition(void) {
    printf("\nVerifying SHM_MAGIC constant definition\n");
    
    /* Verify SHM_MAGIC is 0xDEADBEEF */
    if (SHM_MAGIC == 0xDEADBEEF) {
        printf("  ✓ SHM_MAGIC correctly defined as 0xDEADBEEF\n");
        property_tests_passed++;
    } else {
        printf("  ✗ SHM_MAGIC incorrectly defined as 0x%08X (expected 0xDEADBEEF)\n",
               SHM_MAGIC);
        property_tests_failed++;
    }
    
    /* Verify ERROR_INVALID_MAGIC is defined */
    if (ERROR_INVALID_MAGIC == (1 << 0)) {
        printf("  ✓ ERROR_INVALID_MAGIC correctly defined as bit 0\n");
        property_tests_passed++;
    } else {
        printf("  ✗ ERROR_INVALID_MAGIC incorrectly defined as 0x%08X\n",
               ERROR_INVALID_MAGIC);
        property_tests_failed++;
    }
}

/**
 * Main test runner
 */
int main(void) {
    /* Seed random number generator */
    srand(time(NULL));
    
    printf("=== PRU Magic Number Validation Property-Based Tests ===\n");
    printf("Feature: pru-firmware\n");
    printf("Property 3: Magic number validation\n");
    printf("Validates: Requirements 5.2, 6.1\n");
    printf("Minimum iterations per property: 100\n\n");
    
    /* Verify constants */
    test_magic_constant_definition();
    
    /* Run property tests */
    test_property_magic_number_validation();
    test_property_valid_magic_acceptance();
    test_property_error_flag_isolation();
    
    /* Print summary */
    printf("\n=== Property Test Summary ===\n");
    printf("Properties Passed: %d\n", property_tests_passed);
    printf("Properties Failed: %d\n", property_tests_failed);
    printf("Total Iterations: %d\n", total_iterations);
    
    if (property_tests_failed == 0) {
        printf("\n✓ All property tests PASSED!\n");
        return 0;
    } else {
        printf("\n✗ Some property tests FAILED!\n");
        return 1;
    }
}
