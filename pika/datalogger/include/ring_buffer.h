#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/**
 * A lock-free Single-Producer Single-Consumer (SPSC) ring buffer
 * designed for high-speed samples.
 */

typedef struct {
  uint8_t *data;
  size_t element_size;
  size_t capacity;
  atomic_size_t head; // Read index
  atomic_size_t tail; // Write index
} ring_buffer_t;

/**
 * Initializes the ring buffer.
 * Elements are chunks of memory of size element_size.
 */
int ring_buffer_init(ring_buffer_t *rb, size_t capacity, size_t element_size);

/**
 * Frees the ring buffer memory.
 */
void ring_buffer_free(ring_buffer_t *rb);

/**
 * Attempts to push an element into the buffer.
 * Copies element_size bytes from src.
 * Returns true on success, false if buffer is full.
 */
bool ring_buffer_push(ring_buffer_t *rb, const void *src);

/**
 * Attempts to pop an element from the buffer.
 * Copies element_size bytes to dest.
 * Returns true on success, false if buffer is empty.
 */
bool ring_buffer_pop(ring_buffer_t *rb, void *dest);

/**
 * Returns number of elements currently in the buffer.
 */
size_t ring_buffer_count(ring_buffer_t *rb);

#endif // RING_BUFFER_H
