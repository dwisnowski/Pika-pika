"""Recent data API endpoint handler.

Provides access to recent voltage measurements from the datalogger.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo as _demo


def api_recent(logger, seconds: float = 5.0, demo: bool = False):
    """Get recent data points from the datalogger.
    
    Args:
        logger: Datalogger instance
        seconds: Number of seconds of recent data to retrieve
        
    Returns:
        JSON response with recent data points
    """
    if demo:
        data = _demo.recent(seconds=seconds, max_points=2000)
    else:
        data = logger.get_recent(seconds=seconds)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})


def register_api_recent_routes(app: FastAPI, logger):
    """Register recent data API routes with the FastAPI app."""
    app.get("/api/recent")(lambda seconds=5.0, demo=False: api_recent(logger, seconds, demo))
