#include "decimator.h"

void decimator_init(decimator_t *dec, uint32_t rate) {
  dec->rate = rate;
  dec->count = 0;
}

int decimator_process(decimator_t *dec) {
  dec->count++;
  if (dec->count >= dec->rate) {
    dec->count = 0;
    return 1;
  }
  return 0;
}
