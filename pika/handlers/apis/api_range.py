"""Range data API endpoint handler.

Provides downsampled data for specified time ranges.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo as _demo


def register_api_range_routes(app: FastAPI, logger):
    """Register range data API routes with the FastAPI app."""
    app.get("/api/range")(lambda start, end, max_points=1000, demo=False: api_range(logger, start, end, max_points, demo))


def api_range(logger, start: float, end: float, max_points: int = 1000, demo: bool = False):
    """Return downsampled data for the requested time range (epoch seconds).
    
    Args:
        logger: Datalogger instance
        start: Start timestamp (epoch seconds)
        end: End timestamp (epoch seconds)
        max_points: Maximum number of data points to return
        
    Returns:
        JSON response with downsampled data points
    """
    try:
        start = float(start)
        end = float(end)
        max_points = int(max_points)
    except Exception:
        return JSONResponse({"data": []})
    if demo:
        data = _demo.range_query(start, end, max_points=max_points)
    else:
        data = logger.get_range(start, end, max_points=max_points)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})
