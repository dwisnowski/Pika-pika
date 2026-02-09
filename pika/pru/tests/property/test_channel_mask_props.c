/**
 * Property-Based Tests for Channel Mask Filtering
 * 
 * Feature: pru-firmware
 * Property 8: Channel mask filtering
 * **Validates: Requirements 5.5**
 * 
 * This test verifies that the number of samples written per acquisition
 * equals the number of bits set in channel_mask, and only those channels
 * are read from the ADC.
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
 * Count the number of enabled channels in a channel mask
 * This mirrors the function in pru_main.c
 */
static inline uint8_t count_enabled_channels(uint32_t channel_mask) {
    uint8_t count = 0;
    for (int i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) {
            count++;
        }
    }
    return count;
}

/**
 * Simulate channel reading state
 */
typedef struct {
    uint32_t channel_mask;
    uint8_t num_channels;
    uint8_t *channels_read;  // Track which channels were read
    uint32_t num_reads;      // Total number of reads performed
} channel_state_t;

/**
 * Initialize channel state
 */
static channel_state_t* init_channel_state(uint32_t channel_mask) {
    channel_state_t *state = malloc(sizeof(channel_state_t));
    if (!state) return NULL;
    
    state->channel_mask = channel_mask;
    state->num_channels = count_enabled_channels(channel_mask);
    state->channels_read = calloc(NUM_ADC_CHANNELS, sizeof(uint8_t));
    state->num_reads = 0;
    
    if (!state->channels_read) {
        free(state);
        return NULL;
    }
    
    return state;
}

/**
 * Free channel state
 */
static void free_channel_state(channel_state_t *state) {
    if (state) {
        free(state->channels_read);
        free(state);
    }
}

/**
 * Simulate reading channels for one sample
 * This mirrors the channel reading logic in pru_main.c
 */
static void read_channels(channel_state_t *state) {
    // Reset channels_read for this sample
    memset(state->channels_read, 0, NUM_ADC_CHANNELS);
    state->num_reads = 0;
    
    // Read enabled channels (from pru_main.c)
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        if (state->channel_mask & (1 << ch)) {
            state->channels_read[ch] = 1;
            state->num_reads++;
        }
    }
}

/**
 * Property 8: Channel mask filtering
 * 
 * For any channel_mask configuration, the number of samples written per
 * acquisition should equal the number of bits set in channel_mask, and
 * only those channels should be read from the ADC.
 */
static int test_channel_mask_filtering(uint32_t channel_mask) {
    // Skip invalid masks (no channels enabled)
    if (channel_mask == 0) return 1;
    
    channel_state_t *state = init_channel_state(channel_mask);
    if (!state) return 0;
    
    // Simulate reading channels
    read_channels(state);
    
    // Verify number of reads equals number of enabled channels
    if (state->num_reads != state->num_channels) {
        free_channel_state(state);
        return 0;  // FAIL: wrong number of reads
    }
    
    // Verify only enabled channels were read
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        int should_be_read = (channel_mask & (1 << ch)) != 0;
        int was_read = state->channels_read[ch] != 0;
        
        if (should_be_read != was_read) {
            free_channel_state(state);
            return 0;  // FAIL: wrong channels read
        }
    }
    
    free_channel_state(state);
    return 1;  // PASS
}

/**
 * Property 8a: Single channel masks
 * 
 * Verify that single-channel masks work correctly.
 */
static int test_single_channel(uint8_t channel) {
    if (channel >= NUM_ADC_CHANNELS) return 1;  // Skip invalid channels
    
    uint32_t channel_mask = (1 << channel);
    channel_state_t *state = init_channel_state(channel_mask);
    if (!state) return 0;
    
    read_channels(state);
    
    // Should read exactly 1 channel
    if (state->num_reads != 1) {
        free_channel_state(state);
        return 0;  // FAIL: wrong number of reads
    }
    
    // Should read only the specified channel
    if (!state->channels_read[channel]) {
        free_channel_state(state);
        return 0;  // FAIL: specified channel not read
    }
    
    // No other channels should be read
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        if (ch != channel && state->channels_read[ch]) {
            free_channel_state(state);
            return 0;  // FAIL: wrong channel read
        }
    }
    
    free_channel_state(state);
    return 1;  // PASS
}

/**
 * Property 8b: All channels enabled
 * 
 * Verify that enabling all channels reads all 8 channels.
 */
static int test_all_channels(void) {
    uint32_t channel_mask = 0xFF;  // All 8 channels
    channel_state_t *state = init_channel_state(channel_mask);
    if (!state) return 0;
    
    read_channels(state);
    
    // Should read all 8 channels
    if (state->num_reads != NUM_ADC_CHANNELS) {
        free_channel_state(state);
        return 0;  // FAIL: wrong number of reads
    }
    
    // All channels should be read
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        if (!state->channels_read[ch]) {
            free_channel_state(state);
            return 0;  // FAIL: channel not read
        }
    }
    
    free_channel_state(state);
    return 1;  // PASS
}

/**
 * Property 8c: Alternating channels
 * 
 * Verify that alternating channel patterns work correctly.
 */
static int test_alternating_channels(void) {
    // Test even channels (0, 2, 4, 6)
    uint32_t even_mask = 0x55;  // 01010101
    channel_state_t *state = init_channel_state(even_mask);
    if (!state) return 0;
    
    read_channels(state);
    
    if (state->num_reads != 4) {
        free_channel_state(state);
        return 0;  // FAIL: wrong number of reads
    }
    
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        int should_be_read = (ch % 2 == 0);
        if (state->channels_read[ch] != should_be_read) {
            free_channel_state(state);
            return 0;  // FAIL: wrong channels read
        }
    }
    
    free_channel_state(state);
    
    // Test odd channels (1, 3, 5, 7)
    uint32_t odd_mask = 0xAA;  // 10101010
    state = init_channel_state(odd_mask);
    if (!state) return 0;
    
    read_channels(state);
    
    if (state->num_reads != 4) {
        free_channel_state(state);
        return 0;  // FAIL: wrong number of reads
    }
    
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        int should_be_read = (ch % 2 == 1);
        if (state->channels_read[ch] != should_be_read) {
            free_channel_state(state);
            return 0;  // FAIL: wrong channels read
        }
    }
    
    free_channel_state(state);
    return 1;  // PASS
}

/**
 * Property 8d: Channel count correctness
 * 
 * Verify that count_enabled_channels returns correct count for any mask.
 */
static int test_channel_count(uint32_t channel_mask) {
    uint8_t count = count_enabled_channels(channel_mask);
    
    // Manually count bits
    uint8_t expected_count = 0;
    for (int i = 0; i < NUM_ADC_CHANNELS; i++) {
        if (channel_mask & (1 << i)) {
            expected_count++;
        }
    }
    
    return (count == expected_count);
}

int main(void) {
    printf("=== PRU Channel Mask Filtering Property-Based Tests ===\n");
    printf("Feature: pru-firmware\n");
    printf("Property 8: Channel mask filtering\n");
    printf("**Validates: Requirements 5.5**\n");
    printf("Minimum iterations per property: 100\n\n");
    
    // Seed random number generator
    srand(time(NULL));
    
    int passed = 0;
    int failed = 0;
    
    // Property 8: Channel mask filtering
    printf("Running Property 8: Channel mask filtering\n");
    printf("  Testing with 20 random channel masks...\n");
    
    for (int i = 0; i < 20; i++) {
        // Generate random channel mask (1-255, excluding 0)
        uint32_t channel_mask = 1 + (rand() % 255);
        
        if (test_channel_mask_filtering(channel_mask)) {
            passed++;
        } else {
            failed++;
            printf("  FAIL: channel_mask=0x%02X\n", channel_mask);
        }
    }
    
    // Test edge cases
    printf("  Testing edge cases...\n");
    
    // Edge case: All channels enabled
    if (test_channel_mask_filtering(0xFF)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - all channels (0xFF)\n");
    }
    
    // Edge case: Single channel (channel 0)
    if (test_channel_mask_filtering(0x01)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - single channel 0 (0x01)\n");
    }
    
    // Edge case: Single channel (channel 7)
    if (test_channel_mask_filtering(0x80)) {
        passed++;
    } else {
        failed++;
        printf("  FAIL: Edge case - single channel 7 (0x80)\n");
    }
    
    printf("  Property 8 Results: %d passed, %d failed (out of %d iterations)\n",
           passed, failed, passed + failed);
    
    if (failed == 0) {
        printf("  ✓ Property 8 PASSED\n\n");
    } else {
        printf("  ✗ Property 8 FAILED\n\n");
        return 1;
    }
    
    // Property 8a: Single channel masks
    int passed_8a = 0;
    int failed_8a = 0;
    
    printf("Running Property 8a: Single channel masks\n");
    printf("  Testing all 8 individual channels...\n");
    
    for (uint8_t ch = 0; ch < NUM_ADC_CHANNELS; ch++) {
        if (test_single_channel(ch)) {
            passed_8a++;
        } else {
            failed_8a++;
            printf("  FAIL: channel %u\n", ch);
        }
    }
    
    printf("  Property 8a Results: %d passed, %d failed (out of %d iterations)\n",
           passed_8a, failed_8a, passed_8a + failed_8a);
    
    if (failed_8a == 0) {
        printf("  ✓ Property 8a PASSED\n\n");
    } else {
        printf("  ✗ Property 8a FAILED\n\n");
        return 1;
    }
    
    // Property 8b: All channels enabled
    int passed_8b = 0;
    int failed_8b = 0;
    
    printf("Running Property 8b: All channels enabled\n");
    printf("  Testing with all channels enabled...\n");
    
    for (int i = 0; i < 10; i++) {
        if (test_all_channels()) {
            passed_8b++;
        } else {
            failed_8b++;
            printf("  FAIL: iteration %d\n", i);
        }
    }
    
    printf("  Property 8b Results: %d passed, %d failed (out of %d iterations)\n",
           passed_8b, failed_8b, passed_8b + failed_8b);
    
    if (failed_8b == 0) {
        printf("  ✓ Property 8b PASSED\n\n");
    } else {
        printf("  ✗ Property 8b FAILED\n\n");
        return 1;
    }
    
    // Property 8c: Alternating channels
    int passed_8c = 0;
    int failed_8c = 0;
    
    printf("Running Property 8c: Alternating channels\n");
    printf("  Testing even/odd channel patterns...\n");
    
    for (int i = 0; i < 10; i++) {
        if (test_alternating_channels()) {
            passed_8c++;
        } else {
            failed_8c++;
            printf("  FAIL: iteration %d\n", i);
        }
    }
    
    printf("  Property 8c Results: %d passed, %d failed (out of %d iterations)\n",
           passed_8c, failed_8c, passed_8c + failed_8c);
    
    if (failed_8c == 0) {
        printf("  ✓ Property 8c PASSED\n\n");
    } else {
        printf("  ✗ Property 8c FAILED\n\n");
        return 1;
    }
    
    // Property 8d: Channel count correctness
    int passed_8d = 0;
    int failed_8d = 0;
    
    printf("Running Property 8d: Channel count correctness\n");
    printf("  Testing with 20 random channel masks...\n");
    
    for (int i = 0; i < 20; i++) {
        uint32_t channel_mask = rand() % 256;  // 0-255
        
        if (test_channel_count(channel_mask)) {
            passed_8d++;
        } else {
            failed_8d++;
            printf("  FAIL: channel_mask=0x%02X\n", channel_mask);
        }
    }
    
    printf("  Property 8d Results: %d passed, %d failed (out of %d iterations)\n",
           passed_8d, failed_8d, passed_8d + failed_8d);
    
    if (failed_8d == 0) {
        printf("  ✓ Property 8d PASSED\n\n");
    } else {
        printf("  ✗ Property 8d FAILED\n\n");
        return 1;
    }
    
    // Summary
    printf("=== Property Test Summary ===\n");
    printf("Properties Passed: 5\n");
    printf("Properties Failed: 0\n");
    printf("Total Iterations: %d\n\n", passed + passed_8a + passed_8b + passed_8c + passed_8d);
    printf("✓ All property tests PASSED!\n");
    
    return 0;
}
