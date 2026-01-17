"""Health check endpoint handler.

Provides health status information for monitoring and systemd checks.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def health(logger):
    """Simple health endpoint useful for monitoring and systemd checks.

    Returns:
      - status: 'ok' | 'degraded' | 'fail'
      - last_sample_age: seconds since last sample (or null if none)
      - recent_count: number of recent samples in 10s window
    """
    import time as _time
    recent = logger.get_recent(seconds=10.0)
    last_sample_age = None
    if recent:
        last_sample_age = _time.time() - recent[-1][0]
    status = 'ok'
    if last_sample_age is None or last_sample_age > 3.0:
        status = 'degraded'
    return JSONResponse({
        "status": status, 
        "last_sample_age": last_sample_age, 
        "recent_count": len(recent)
    })


def register_health_routes(app: FastAPI, logger):
    """Register health check routes with the FastAPI app."""
    app.get('/health')(lambda: health(logger))
