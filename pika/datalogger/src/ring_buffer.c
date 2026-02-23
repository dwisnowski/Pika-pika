#include "ring_buffer.h"
#include <stdlib.h>
#include <string.h>

int ring_buffer_init(ring_buffer_t *rb, size_t capacity, size_t element_size) {
  rb->data = malloc(capacity * element_size);
  if (!rb->data)
    return -1;

  rb->capacity = capacity;
  rb->element_size = element_size;
  atomic_init(&rb->head, 0);
  atomic_init(&rb->tail, 0);

  return 0;
}

void ring_buffer_free(ring_buffer_t *rb) {
  if (rb->data) {
    free(rb->data);
    rb->data = NULL;
  }
}

bool ring_buffer_push(ring_buffer_t *rb, const void *src) {
  size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_relaxed);
  size_t current_head = atomic_load_explicit(&rb->head, memory_order_acquire);

  size_t next_tail = (current_tail + 1) % rb->capacity;

  if (next_tail == current_head) {
    // Buffer full
    return false;
  }

  memcpy(rb->data + (current_tail * rb->element_size), src, rb->element_size);

  atomic_store_explicit(&rb->tail, next_tail, memory_order_release);
  return true;
}

bool ring_buffer_pop(ring_buffer_t *rb, void *dest) {
  size_t current_head = atomic_load_explicit(&rb->head, memory_order_relaxed);
  size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_acquire);

  if (current_head == current_tail) {
    // Buffer empty
    return false;
  }

  memcpy(dest, rb->data + (current_head * rb->element_size), rb->element_size);

  size_t next_head = (current_head + 1) % rb->capacity;
  atomic_store_explicit(&rb->head, next_head, memory_order_release);

  return true;
}

size_t ring_buffer_count(ring_buffer_t *rb) {
  size_t current_tail = atomic_load_explicit(&rb->tail, memory_order_relaxed);
  size_t current_head = atomic_load_explicit(&rb->head, memory_order_relaxed);

  if (current_tail >= current_head) {
    return current_tail - current_head;
  } else {
    return rb->capacity - (current_head - current_tail);
  }
}
