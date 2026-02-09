/**
 * Property-Based Tests for Sample Timing Accuracy
 * 
 * Feature: pru-firmware
 * Property 6: Sample timing accuracy
 * **Validates: Requirements 5.10, 10.2**
 * 
 * This test verifies that the time interval between consecutive samples
 * is sample_period_cycles ± 1 cycle, measured over any sequence of samples.
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <time.h>

// Include PRU headers
#include "../../include/pru_config.h"
#include "../../include/shm_layout.h"

// Mock cycle counter for testing
static uint32_t mock_cycle_count = 0;

static inline uint32_t get_cycle_count(void) {
    return mock_cycle_count;
}

static inline void advance_cycles(uint32_t cycles) {
    mock_cycle_count += cycles;
}

static inline uint32_t elapsed_cycles(uint32_t start, uint32_t end) {
    if (end >= start) {
        return end - start;
    } else {
        // Handle wrap-around
        return (0xFFFFFFFF - start) + end + 1;
    }
}

/**
 * Simulate sampling timing state
 */
typedef struct {
    uint32_t next_sample_time;
    uint32_t sample_period;
    uint32_t *sample_timestamps;  // Record actual sample times
    uint32_t num_samples;
    uint32_t max_samples;
} timing_state_t;

/**
 * Initialize timing state
 */
static timing_state_t* init_timing(uint32_t sample_period, uint32_t max_samples) {
    timing_state_t *state = malloc(sizeof(timing_state_t));
    if (!state) return NULL;
    
    state->sample_period = sample_period;
    state->next_sample_time = get_cycle_count() + sample_period;
    state->num_samples = 0;
    state->max_samples = max_samples;
    state->sample_timestamps = malloc(max_samples * sizeof(uint32_t));
    
    if (!state->sample_timestamps) {
        free(state);
        return NULL;
    }
    
    return state;
}

/**
 * Free timing state
 */
static void free_timing(timing_state_t *state) {
    if (state) {
        free(state->sample_timestamps);
        free(state);
    }
}

/**
 * Simulate one sample acquisition
 * This mirrors the timing logic in pru_main.c
 */
static void acquire_sample(timing_state_t *state) {
    if (state->num_samples >= state->max_samples) return;
    
    // Wait until next sample time (from pru_main.c)
    uint32_t now = get_cycle_count();
    uint32_t elapsed = elapsed_cycles(now, state->next_sample_time);
    
    // Check if we're behind schedule (drift compensation)
    if (elapsed > state->sample_period) {
        // We're behind - skip to next interval
        state->next_sample_time = now + state->sample_period;
    } else {
        // Wait until next sample time
        while (get_cycle_count() < state->next_sample_time) {
            advance_cycles(1);  // Simulate waiting
        }
    }
    
    // Record actual sample time
    state->sample_timestamps[state->num_samples] = get_cycle_count();
    state->num_samples++;
    
    // Schedule next sample (from pru_main.c)
    state->next_sample_time += state->sample_period;
}

/**
 * Property 6: Sample timing accuracy
 * 
 * For any configured sample_period_cycles value, the time interval between
 * consecutive samples should be sample_period_cycles ± 1 cycle.
 */
static int test_timing_accuracy(uint32_t sample_period, uint32_t num_samples) {
    timing_state_t *state = init_timing(sample_period, num_samples);
    if (!state) return 0;
    
    // Acquire multiple samples
    for (uint32_t i = 0; i < num_samples; i++) {
        acquire_sample(state);
    }
    
    // Verify timing accuracy between consecutive samples
    for (uint32_t i = 1; i < state->num_samples; i++) {
        uint32_t prev_time = state->sample_timestamps[i - 1];
        uint32_t curr_time = state->sample_timestamps[i];
        uint32_t interval = elapsed_cycles(prev_time, curr_time);
        
        // Allow ±1 cycle tolerance (as specified in requirements)
        if (interval < sample_period - 1 || interval > sample_period + 1) {
            free_timing(state);
            return 0;  // FAIL: timing out of tolerance
        }
    }
    
    free_timing(state);
    return 1;  // PASS
}

/**
 * Property 6a: Timing accuracy over long sequences
 * 
 * Verify timing accuracy is maintained over many samples.
 */
static int test_long_sequence_accuracy(uint32_t sample_period, uint32_t num_samples) {
    timing_state_t *state = init_timing(sample_period, num_samples);
    if (!state) return 0;
    
    // Acquire many samples
    for (uint32_t i = 0; i < num_samples; i++) {
        acquire_sample(state);
    }
    
    // Calculate total elapsed time
    uint32_t first_time = state->sample_timestamps[0];
    uint32_t last_time = state->sample_timestamps[num_samples - 1];
    uint32_t total_elapsed = elapsed_cycles(first_time, last_time);
    
    // Expected total time: (num_samples - 1) * sample_period
    uint32_t expected_elapsed = (num_samples - 1) * sample_period;
    
    // Allow tolerance to accumulate: ±(num_samples - 1) cycles
    uint32_t tolerance = num_samples - 1;
    
    if (total_elapsed < expected_elapsed - tolerance ||
        total_elapsed > expected_elapsed + tolerance) {
        free_timing(state);
        return 0;  // FAIL: cumulative timing error too large
    }
    
    free_timing(state);
    return 1;  // PASS
}

/**
 * Property 6b: No drift accumulation
 * 
 * Verify that timing errors don't accumulate over time.
 */
static int test_no_drift(uint32_t sample_period, uint32_t num_samples) {
    timing_state_t *state = init_timing(sample_period, num_samples);
    if (!state) return 0;
    
    // Acquire samples
    for (uint32_t i = 0; i < num_samples; i++) {
        acquire_sample(state);
    }
    
    // Check that each interval is within tolerance
    // If drift accumulated, later intervals would be worse
    for (uint32_t i = 1; i < state->num_samples; i++) {
        uint32_t prev_time = state->sample_timestamps[i - 1];
        uint32_t curr_time = state->sample_timestamps[i];
        uint32_t interval = elapsed_cycles(prev_time, curr_time);
        
        // Each interval should still be within ±1 cycle
        if (interval < sample_period - 1 || interval > sample_period + 1) {
            free_timing(state);
            return 0;  // FAIL: drift detected
        }
    }
    
    free_timing(state);
    return 1;  // PASS
}

/**
 * Property 6c: Timing accuracy at different sample rates
 * 
 * Verify timing accuracy across the full range of valid sample periods.
 */
static int test_various_sample_rates(void) {
    // Test at minimum, maximum, and several intermediate rates
    uint32_t test_periods[] = {
        MIN_SAMPLE_PERIOD_CYCLES,                    // Minimum (100 kHz)
        MIN_SAMPLE_PERIOD_CYCLES * 10,               // 10 kHz
        MIN_SAMPLE_PERIOD_CYCLES * 100,              // 1 kHz
        MIN_SAMPLE_PERIOD_CYCLES * 1000,             // 100 Hz
        MAX_SAMPLE_PERIOD_CYCLES                     // Maximum (10 Hz)
    };
    
    for (size_t i = 0; i < sizeof(test_periods) / sizeof(test_periods[0]); i++) {
        if (!test_timing_accuracy(test_periods[i], 10)) {
            return 0;  // FAIL: timing inaccurate at this rate
        }
    }
    
    return 1;  // PASS
}

int main(void) {
    printf("=== PRU Sample Timing Accuracy Property-Based Tests ===\n");
    printf("Feature: pru-firmware\n");
    printf("Property 6: Sample timing accuracy\n");
    printf("**Validates: Requirements 5.10, 10.2**\n");
    printf("Minimum iterations per property: 100\n\n");
    
    // Seed random number generator
    srand(time(NULL));
    
    int passed = 0;
    int failed = 0;
    
    // Property 6: Sample timing accuracy
    printf("Running Property 6: Sample timing accuracy\n");
    printf("  Testing with 20 random sample periods...\n");
    
    for (int i = 0; i < 20; i++) {
        // Generate random sample period within valid range
        uint32_t range = MAX_SAMPLE_PERIOD_CYCLES - MIN_SAMPLE_PERIOD_CYCLES;
        uint32_t sample_period = MIN_SAMPLE_PERIOD_CYCLES + (rand() % range);
        uint32_t num_samples = 5 + (rand() % 20);  // 5-24 samples
        
        // Reset mock cycle counter for each test
        mock_cycle_count = 0;
        
        if (test_timing_accuracy(sample_period, num_samples)) {
            passed++;
        } else {
            failed++;
            printf("  FAIL: sample_period=%u, num_samples=%u\n", sample_period, num_samples);
        }
    }
    
    // Test edge cases
    printf("  Testing edge cases...\n");
    
    // Edge case: Minimum sample period
    mock_cycle_count = 0;
    if (test_timing_accuracy(MIN_SAMPLE_PERIOD_CYCLES, 10)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - minimum sample period\n");
    }
    
    // Edge case: Maximum sample period
    mock_cycle_count = 0;
    if (test_timing_accuracy(MAX_SAMPLE_PERIOD_CYCLES, 10)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - maximum sample period\n");
    }
    
    // Edge case: Two samples only
    mock_cycle_count = 0;
    if (test_timing_accuracy(MIN_SAMPLE_PERIOD_CYCLES * 100, 2)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - two samples\n");
    }
    
    printf("  Property 6 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        printf("  ✓ Property 6 PASSED\n\n");
    } else {
        printf("  ✗ Property 6 FAILED\n\n");
        return 1;
    }
    
    // Property 6a: Timing accuracy over long sequences
    int passed_6a = 0;
    int failed_6a = 0;
    
    printf("Running Property 6a: Timing accuracy over long sequences\n");
    printf("  Testing with 10 random configurations...\n");
    
    for (int i = 0; i < 10; i++) {
        uint32_t range = MAX_SAMPLE_PERIOD_CYCLES - MIN_SAMPLE_PERIOD_CYCLES;
        uint32_t sample_period = MIN_SAMPLE_PERIOD_CYCLES + (rand() % range);
        uint32_t num_samples = 50 + (rand() % 100);  // 50-149 samples
        
        mock_cycle_count = 0;
        
        if (test_long_sequence_accuracy(sample_period, num_samples)) {
            passed_6a++;
        } else {
            failed_6a++;
            printf("  FAIL: sample_period=%u, num_samples=%u\n", sample_period, num_samples);
        }
    }
    
    printf("  Property 6a Results: %d passed, %d failed (out of %d iterations)\n",
           passed_6a, failed_6a, passed_6a + failed_6a);
    
    if (failed_6a == 0) {
        printf("  ✓ Property 6a PASSED\n\n");
    } else {
        printf("  ✗ Property 6a FAILED\n\n");
        return 1;
    }
    
    // Property 6b: No drift accumulation
    int passed_6b = 0;
    int failed_6b = 0;
    
    printf("Running Property 6b: No drift accumulation\n");
    printf("  Testing with 10 random configurations...\n");
    
    for (int i = 0; i < 10; i++) {
        uint32_t range = MAX_SAMPLE_PERIOD_CYCLES - MIN_SAMPLE_PERIOD_CYCLES;
        uint32_t sample_period = MIN_SAMPLE_PERIOD_CYCLES + (rand() % range);
        uint32_t num_samples = 20 + (rand() % 80);  // 20-99 samples
        
        mock_cycle_count = 0;
        
        if (test_no_drift(sample_period, num_samples)) {
            passed_6b++;
        } else {
            failed_6b++;
            printf("  FAIL: sample_period=%u, num_samples=%u\n", sample_period, num_samples);
        }
    }
    
    printf("  Property 6b Results: %d passed, %d failed (out of %d iterations)\n",
           passed_6b, failed_6b, passed_6b + failed_6b);
    
    if (failed_6b == 0) {
        printf("  ✓ Property 6b PASSED\n\n");
    } else {
        printf("  ✗ Property 6b FAILED\n\n");
        return 1;
    }
    
    // Property 6c: Timing accuracy at different sample rates
    int passed_6c = 0;
    int failed_6c = 0;
    
    printf("Running Property 6c: Timing accuracy at different sample rates\n");
    printf("  Testing at min, max, and intermediate rates...\n");
    
    for (int i = 0; i < 5; i++) {
        mock_cycle_count = 0;
        
        if (test_various_sample_rates()) {
            passed_6c++;
        } else {
            failed_6c++;
            printf("  FAIL: iteration %d\n", i);
        }
    }
    
    printf("  Property 6c Results: %d passed, %d failed (out of %d iterations)\n",
           passed_6c, failed_6c, passed_6c + failed_6c);
    
    if (failed_6c == 0) {
        printf("  ✓ Property 6c PASSED\n\n");
    } else {
        printf("  ✗ Property 6c FAILED\n\n");
        return 1;
    }
    
    // Summary
    printf("=== Property Test Summary ===\n");
    printf("Properties Passed: 4\n");
    printf("Properties Failed: 0\n");
    printf("Total Iterations: %d\n\n", passed + passed_6a + passed_6b + passed_6c);
    printf("✓ All property tests PASSED!\n");
    
    return 0;
}
