#ifndef PIKA_LOG_H
#define PIKA_LOG_H

#include <stdio.h>

/**
 * Returns 1 when PIKA_DEBUG is set to a non-empty value other than "0".
 * Result is cached after the first call.
 */
int pika_debug_enabled(void);

/** Progress/tick printf gated by PIKA_DEBUG (off by default). */
#define PIKA_DBG(...)                                                          \
  do {                                                                         \
    if (pika_debug_enabled())                                                  \
      printf(__VA_ARGS__);                                                     \
  } while (0)

#endif /* PIKA_LOG_H */
