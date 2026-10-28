#include "log.h"

#include <stdlib.h>
#include <string.h>

int pika_debug_enabled(void) {
  static int cached = -1;
  if (cached < 0) {
    const char *v = getenv("PIKA_DEBUG");
    cached = (v != NULL && v[0] != '\0' && strcmp(v, "0") != 0) ? 1 : 0;
  }
  return cached;
}
