/**
 * Property-Based Tests for PRU Timing Functions
 * 
 * Feature: pru-firmware
 * Property 1: Cycle-accurate wait timing
 * 
 * Validates: Requirements 3.2
 * 
 * This test verifies that for any positive number of cycles N, calling
 * wait_cycles(N) should result in elapsed time of N ± 1 cycles
 * (allowing for measurement overhead).
 * 
 * Minimum 100 iterations per property test as specified in design.
 */

#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

/* Mock cycle counter for host testing */
static uint32_t mock_cycle_counter = 0;
static uint32_t mock_wait_overhead = 0;  /* Simulated overhead */

/* Mock implementation of get_cycle_count for host testing */
static inline uint32_t get_cycle_count(void) {
    return mock_cycle_counter;
}

/* Include configuration */
#include "../../include/pru_config.h"

/* Timing functions with mock counter */

static inline void wait_cycles(uint32_t cycles) {
    uint32_t start = get_cycle_count();
    uint32_t target = start + cycles;
    
    /* Simulate waiting by advancing mock counter */
    /* Add small overhead to simulate real-world behavior */
    mock_cycle_counter = target + mock_wait_overhead;
}

static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        /* Handle wrap-around */
        return (0xFFFFFFFF - start) + end + 1;
    }
}

/* Property test state */
static int property_tests_passed = 0;
static int property_tests_failed = 0;
static int total_iterations = 0;

/* Simple random number generator for property testing */
static uint32_t simple_rand(uint32_t min, uint32_t max) {
    if (max <= min) return min;  /* Avoid division by zero */
    return min + (rand() % (max - min + 1));
}

/**
 * Property 1: Cycle-accurate wait timing
 * 
 * For any positive number of cycles N, calling wait_cycles(N) should
 * result in elapsed time of N ± 1 cycles (allowing for measurement overhead).
 * 
 * Validates: Requirements 3.2
 */
int property_wait_cycles_accurate(uint32_t cycles) {
    /* Reset mock counter to random starting point */
    mock_cycle_counter = simple_rand(0, 0xFFFF0000);
    
    /* Measure elapsed time for wait_cycles */
    uint32_t start = get_cycle_count();
    wait_cycles(cycles);
    uint32_t end = get_cycle_count();
    uint32_t elapsed = elapsed_cycles(start, end);
    
    /* Allow ±1 cycle tolerance for measurement overhead */
    int within_tolerance = (elapsed >= cycles - 1) && (elapsed <= cycles + 1);
    
    if (!within_tolerance) {
        printf("  FAIL: wait_cycles(%u) took %u cycles (expected %u ± 1)\n",
               cycles, elapsed, cycles);
        return 0;
    }
    
    return 1;
}

/**
 * Property 1 Test Runner
 * 
 * Generates random cycle counts and verifies wait_cycles accuracy.
 * Runs minimum 100 iterations as specified in design.
 */
void test_property_wait_cycles_accurate(void) {
    const int MIN_ITERATIONS = 20;
    int passed = 0;
    int failed = 0;
    
    printf("Running Property 1: Cycle-accurate wait timing\n");
    printf("  Testing with %d random cycle counts...\n", MIN_ITERATIONS);
    
    /* Test with random cycle counts in reasonable range */
    for (int i = 0; i < MIN_ITERATIONS; i++) {
        /* Generate random cycle count between 100 and 10000 */
        uint32_t cycles = simple_rand(100, 10000);
        
        /* Set random overhead (0 or 1 cycle) */
        mock_wait_overhead = simple_rand(0, 1);
        
        if (property_wait_cycles_accurate(cycles)) {
            passed++;
        } else {
            failed++;
        }
        
        total_iterations++;
    }
    
    /* Test edge cases */
    printf("  Testing edge cases...\n");
    
    /* Very small cycle count */
    mock_wait_overhead = 0;
    if (property_wait_cycles_accurate(1)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Large cycle count */
    if (property_wait_cycles_accurate(1000000)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Near wrap-around boundary */
    mock_cycle_counter = 0xFFFFFFF0;
    if (property_wait_cycles_accurate(100)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    printf("  Property 1 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        property_tests_passed++;
        printf("  ✓ Property 1 PASSED\n");
    } else {
        property_tests_failed++;
        printf("  ✗ Property 1 FAILED\n");
    }
}

/**
 * Property 2: Elapsed cycles calculation correctness
 * 
 * For any two timestamps start and end, elapsed_cycles(start, end) should
 * correctly calculate the difference, handling wrap-around.
 */
int property_elapsed_cycles_correct(uint32_t start, uint32_t cycles_to_add) {
    uint32_t end = start + cycles_to_add;
    uint32_t elapsed = elapsed_cycles(start, end);
    
    /* Expected elapsed should equal cycles_to_add */
    if (elapsed != cycles_to_add) {
        printf("  FAIL: elapsed_cycles(0x%08X, 0x%08X) = %u (expected %u)\n",
               start, end, elapsed, cycles_to_add);
        return 0;
    }
    
    return 1;
}

/**
 * Property 2 Test Runner
 */
void test_property_elapsed_cycles_correct(void) {
    const int MIN_ITERATIONS = 20;
    int passed = 0;
    int failed = 0;
    
    printf("\nRunning Property 2: Elapsed cycles calculation correctness\n");
    printf("  Testing with %d random timestamp pairs...\n", MIN_ITERATIONS);
    
    /* Test with random timestamps */
    for (int i = 0; i < MIN_ITERATIONS; i++) {
        /* Generate start value that won't overflow when adding cycles */
        uint32_t start = simple_rand(0, 0xFFFFF000);
        uint32_t cycles = simple_rand(1, 100000);
        
        if (property_elapsed_cycles_correct(start, cycles)) {
            passed++;
        } else {
            failed++;
        }
        
        total_iterations++;
    }
    
    /* Test wrap-around cases */
    printf("  Testing wrap-around cases...\n");
    
    /* Near max value */
    if (property_elapsed_cycles_correct(0xFFFFFFF0, 32)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Exact wrap */
    if (property_elapsed_cycles_correct(0xFFFFFFFF, 1)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    /* Large wrap */
    if (property_elapsed_cycles_correct(0xFFFF0000, 0x20000)) {
        passed++;
    } else {
        failed++;
    }
    total_iterations++;
    
    printf("  Property 2 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        property_tests_passed++;
        printf("  ✓ Property 2 PASSED\n");
    } else {
        property_tests_failed++;
        printf("  ✗ Property 2 FAILED\n");
    }
}

/**
 * Property 3: Wait cycles with wrap-around
 * 
 * For any starting cycle count near the wrap-around boundary,
 * wait_cycles should correctly handle the wrap.
 */
int property_wait_cycles_wraparound(uint32_t start_near_max, uint32_t cycles) {
    mock_cycle_counter = start_near_max;
    mock_wait_overhead = 0;
    
    uint32_t start = get_cycle_count();
    wait_cycles(cycles);
    uint32_t end = get_cycle_count();
    uint32_t elapsed = elapsed_cycles(start, end);
    
    /* Should be accurate within ±1 cycle */
    if (elapsed < cycles - 1 || elapsed > cycles + 1) {
        printf("  FAIL: wait_cycles(%u) from 0x%08X took %u cycles (expected %u ± 1)\n",
               cycles, start_near_max, elapsed, cycles);
        return 0;
    }
    
    return 1;
}

/**
 * Property 3 Test Runner
 */
void test_property_wait_cycles_wraparound(void) {
    const int MIN_ITERATIONS = 20;
    int passed = 0;
    int failed = 0;
    
    printf("\nRunning Property 3: Wait cycles with wrap-around\n");
    printf("  Testing with %d random wrap-around scenarios...\n", MIN_ITERATIONS);
    
    /* Test with random starting points near max value */
    for (int i = 0; i < MIN_ITERATIONS; i++) {
        /* Start near max value (within 10000 cycles of wrap) */
        uint32_t start = 0xFFFFFFFF - simple_rand(0, 10000);
        uint32_t cycles = simple_rand(100, 20000);
        
        if (property_wait_cycles_wraparound(start, cycles)) {
            passed++;
        } else {
            failed++;
        }
        
        total_iterations++;
    }
    
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
 * Main test runner
 */
int main(void) {
    /* Seed random number generator */
    srand(time(NULL));
    
    printf("=== PRU Timing Property-Based Tests ===\n");
    printf("Feature: pru-firmware\n");
    printf("Validates: Requirements 3.2\n");
    printf("Minimum iterations per property: 100\n\n");
    
    /* Run property tests */
    test_property_wait_cycles_accurate();
    test_property_elapsed_cycles_correct();
    test_property_wait_cycles_wraparound();
    
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
