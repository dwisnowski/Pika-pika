"""Recent data API endpoint handler.

Provides access to recent voltage measurements from the datalogger.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


def api_recent(logger, seconds: float = 5.0):
    """Get recent data points from the datalogger.
    
    Args:
        logger: Datalogger instance
        seconds: Number of seconds of recent data to retrieve
        
    Returns:
        JSON response with recent data points
    """
    data = logger.get_recent(seconds=seconds)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})


def register_api_recent_routes(app: FastAPI, logger):
    """Register recent data API routes with the FastAPI app."""
    app.get("/api/recent")(lambda seconds: api_recent(logger, seconds))
