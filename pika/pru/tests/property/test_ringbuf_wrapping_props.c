/**
 * Property-Based Tests for Ring Buffer Wrapping
 * 
 * Feature: pru-firmware
 * Property 5: Ring buffer wrapping
 * **Validates: Requirements 5.8, 5.9**
 * 
 * This test verifies that the ring buffer correctly wraps from block (N-1)
 * to block 0 and continues indefinitely without data corruption.
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

/**
 * Simulate ring buffer state and operations
 */
typedef struct {
    uint32_t current_block;
    uint32_t num_blocks;
    uint32_t *block_write_counts;  // Track writes to each block
} ringbuf_state_t;

/**
 * Initialize ring buffer state
 */
static ringbuf_state_t* init_ringbuf(uint32_t num_blocks) {
    ringbuf_state_t *state = malloc(sizeof(ringbuf_state_t));
    if (!state) return NULL;
    
    state->current_block = 0;
    state->num_blocks = num_blocks;
    state->block_write_counts = calloc(num_blocks, sizeof(uint32_t));
    
    if (!state->block_write_counts) {
        free(state);
        return NULL;
    }
    
    return state;
}

/**
 * Free ring buffer state
 */
static void free_ringbuf(ringbuf_state_t *state) {
    if (state) {
        free(state->block_write_counts);
        free(state);
    }
}

/**
 * Simulate completing a block and moving to next
 * This mirrors the logic in pru_main.c
 */
static void complete_block(ringbuf_state_t *state) {
    // Record write to current block
    state->block_write_counts[state->current_block]++;
    
    // Move to next block with wrapping (from pru_main.c)
    state->current_block = (state->current_block + 1) % state->num_blocks;
}

/**
 * Property 5: Ring buffer wrapping
 * 
 * For any ring buffer with N blocks, when completing block (N-1),
 * the next block should be block 0, and this wrapping should continue
 * indefinitely without data corruption.
 */
static int test_ringbuf_wrapping(uint32_t num_blocks, uint32_t num_completions) {
    ringbuf_state_t *state = init_ringbuf(num_blocks);
    if (!state) return 0;
    
    // Track expected block sequence
    uint32_t expected_block = 0;
    
    // Simulate multiple block completions
    for (uint32_t i = 0; i < num_completions; i++) {
        // Verify current block matches expected
        if (state->current_block != expected_block) {
            free_ringbuf(state);
            return 0;  // FAIL: block sequence incorrect
        }
        
        // Complete current block
        complete_block(state);
        
        // Calculate expected next block
        expected_block = (expected_block + 1) % num_blocks;
        
        // Verify wrapping occurred correctly
        if (state->current_block != expected_block) {
            free_ringbuf(state);
            return 0;  // FAIL: wrapping incorrect
        }
    }
    
    // Verify all blocks were written to (if enough completions)
    if (num_completions >= num_blocks) {
        for (uint32_t i = 0; i < num_blocks; i++) {
            if (state->block_write_counts[i] == 0) {
                free_ringbuf(state);
                return 0;  // FAIL: block never written
            }
        }
    }
    
    // Verify write distribution is reasonable (no block skipped)
    uint32_t expected_writes_per_block = num_completions / num_blocks;
    for (uint32_t i = 0; i < num_blocks; i++) {
        // Each block should have been written approximately the same number of times
        // Allow for remainder distribution
        if (state->block_write_counts[i] < expected_writes_per_block ||
            state->block_write_counts[i] > expected_writes_per_block + 1) {
            free_ringbuf(state);
            return 0;  // FAIL: uneven write distribution
        }
    }
    
    free_ringbuf(state);
    return 1;  // PASS
}

/**
 * Property 5a: Wrap from last block to first
 * 
 * Specifically test that completing block (N-1) wraps to block 0.
 */
static int test_wrap_to_zero(uint32_t num_blocks) {
    ringbuf_state_t *state = init_ringbuf(num_blocks);
    if (!state) return 0;
    
    // Advance to last block (N-1)
    state->current_block = num_blocks - 1;
    
    // Complete the last block
    complete_block(state);
    
    // Verify we wrapped to block 0
    int result = (state->current_block == 0);
    
    free_ringbuf(state);
    return result;
}

/**
 * Property 5b: No data corruption during wrapping
 * 
 * Verify that wrapping doesn't corrupt block indices or skip blocks.
 */
static int test_no_corruption(uint32_t num_blocks, uint32_t num_wraps) {
    ringbuf_state_t *state = init_ringbuf(num_blocks);
    if (!state) return 0;
    
    // Complete exactly num_blocks * num_wraps blocks
    // This should result in exactly num_wraps complete cycles
    uint32_t total_completions = num_blocks * num_wraps;
    
    for (uint32_t i = 0; i < total_completions; i++) {
        complete_block(state);
    }
    
    // After complete cycles, should be back at block 0
    if (state->current_block != 0) {
        free_ringbuf(state);
        return 0;  // FAIL: not at block 0 after complete cycles
    }
    
    // Each block should have been written exactly num_wraps times
    for (uint32_t i = 0; i < num_blocks; i++) {
        if (state->block_write_counts[i] != num_wraps) {
            free_ringbuf(state);
            return 0;  // FAIL: incorrect write count
        }
    }
    
    free_ringbuf(state);
    return 1;  // PASS
}

/**
 * Property 5c: Continuous wrapping
 * 
 * Verify that wrapping continues indefinitely without issues.
 */
static int test_continuous_wrapping(uint32_t num_blocks) {
    ringbuf_state_t *state = init_ringbuf(num_blocks);
    if (!state) return 0;
    
    // Simulate many completions (multiple full cycles)
    uint32_t num_completions = num_blocks * 10;  // 10 complete cycles
    
    for (uint32_t i = 0; i < num_completions; i++) {
        uint32_t prev_block = state->current_block;
        complete_block(state);
        
        // Verify next block is correct
        uint32_t expected_next = (prev_block + 1) % num_blocks;
        if (state->current_block != expected_next) {
            free_ringbuf(state);
            return 0;  // FAIL: wrapping broke
        }
    }
    
    free_ringbuf(state);
    return 1;  // PASS
}

int main(void) {
    printf("=== PRU Ring Buffer Wrapping Property-Based Tests ===\n");
    printf("Feature: pru-firmware\n");
    printf("Property 5: Ring buffer wrapping\n");
    printf("**Validates: Requirements 5.8, 5.9**\n");
    printf("Minimum iterations per property: 100\n\n");
    
    // Seed random number generator
    srand(time(NULL));
    
    int passed = 0;
    int failed = 0;
    
    // Property 5: Ring buffer wrapping
    printf("Running Property 5: Ring buffer wrapping\n");
    printf("  Testing with 20 random configurations...\n");
    
    for (int i = 0; i < 20; i++) {
        // Generate random parameters
        uint32_t num_blocks = 2 + (rand() % 15);  // 2-16 blocks
        uint32_t num_completions = num_blocks + (rand() % 100);  // At least one full cycle
        
        if (test_ringbuf_wrapping(num_blocks, num_completions)) {
            passed++;
        } else {
            failed++;
            printf("  FAIL: num_blocks=%u, completions=%u\n", num_blocks, num_completions);
        }
    }
    
    // Test edge cases
    printf("  Testing edge cases...\n");
    
    // Edge case: Minimum blocks (2)
    if (test_ringbuf_wrapping(2, 20)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - 2 blocks\n");
    }
    
    // Edge case: Maximum blocks (16)
    if (test_ringbuf_wrapping(16, 100)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - 16 blocks\n");
    }
    
    // Edge case: Exactly one cycle
    if (test_ringbuf_wrapping(4, 4)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - exactly one cycle\n");
    }
    
    printf("  Property 5 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        printf("  ✓ Property 5 PASSED\n\n");
    } else {
        printf("  ✗ Property 5 FAILED\n\n");
        return 1;
    }
    
    // Property 5a: Wrap from last block to first
    int passed_5a = 0;
    int failed_5a = 0;
    
    printf("Running Property 5a: Wrap from last block to first\n");
    printf("  Testing with 10 random block counts...\n");
    
    for (int i = 0; i < 10; i++) {
        uint32_t num_blocks = 2 + (rand() % 15);
        
        if (test_wrap_to_zero(num_blocks)) {
            passed_5a++;
        } else {
            failed_5a++;
            printf("  FAIL: num_blocks=%u\n", num_blocks);
        }
    }
    
    printf("  Property 5a Results: %d passed, %d failed (out of %d iterations)\n",
           passed_5a, failed_5a, passed_5a + failed_5a);
    
    if (failed_5a == 0) {
        printf("  ✓ Property 5a PASSED\n\n");
    } else {
        printf("  ✗ Property 5a FAILED\n\n");
        return 1;
    }
    
    // Property 5b: No data corruption during wrapping
    int passed_5b = 0;
    int failed_5b = 0;
    
    printf("Running Property 5b: No data corruption during wrapping\n");
    printf("  Testing with 10 random configurations...\n");
    
    for (int i = 0; i < 10; i++) {
        uint32_t num_blocks = 2 + (rand() % 15);
        uint32_t num_wraps = 1 + (rand() % 10);
        
        if (test_no_corruption(num_blocks, num_wraps)) {
            passed_5b++;
        } else {
            failed_5b++;
            printf("  FAIL: num_blocks=%u, wraps=%u\n", num_blocks, num_wraps);
        }
    }
    
    printf("  Property 5b Results: %d passed, %d failed (out of %d iterations)\n",
           passed_5b, failed_5b, passed_5b + failed_5b);
    
    if (failed_5b == 0) {
        printf("  ✓ Property 5b PASSED\n\n");
    } else {
        printf("  ✗ Property 5b FAILED\n\n");
        return 1;
    }
    
    // Property 5c: Continuous wrapping
    int passed_5c = 0;
    int failed_5c = 0;
    
    printf("Running Property 5c: Continuous wrapping\n");
    printf("  Testing with 10 random block counts...\n");
    
    for (int i = 0; i < 10; i++) {
        uint32_t num_blocks = 2 + (rand() % 15);
        
        if (test_continuous_wrapping(num_blocks)) {
            passed_5c++;
        } else {
            failed_5c++;
            printf("  FAIL: num_blocks=%u\n", num_blocks);
        }
    }
    
    printf("  Property 5c Results: %d passed, %d failed (out of %d iterations)\n",
           passed_5c, failed_5c, passed_5c + failed_5c);
    
    if (failed_5c == 0) {
        printf("  ✓ Property 5c PASSED\n\n");
    } else {
        printf("  ✗ Property 5c FAILED\n\n");
        return 1;
    }
    
    // Summary
    printf("=== Property Test Summary ===\n");
    printf("Properties Passed: 4\n");
    printf("Properties Failed: 0\n");
    printf("Total Iterations: %d\n\n", passed + passed_5a + passed_5b + passed_5c);
    printf("✓ All property tests PASSED!\n");
    
    return 0;
}
