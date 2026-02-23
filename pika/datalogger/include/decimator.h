#ifndef DECIMATOR_H
#define DECIMATOR_H

#include <stdint.h>

typedef struct {
  uint32_t rate;
  uint32_t count;
} decimator_t;

void decimator_init(decimator_t *dec, uint32_t rate);

/**
 * Returns true if the current sample should be kept.
 */
int decimator_process(decimator_t *dec);

#endif // DECIMATOR_H
