"""Range data API endpoint handler.

Provides downsampled data for specified time ranges.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo as _demo


import os

def register_api_range_routes(app: FastAPI, logger):
    """Register range data API routes with the FastAPI app."""
    app.get("/api/range")(lambda start, end, max_points=1000, demo=False, source=None: api_range(logger, start, end, max_points, demo, source))


def api_range(logger, start: float, end: float, max_points: int = 1000, demo: bool = False, source: str = None):
    """Return downsampled data for the requested time range (epoch seconds).
    
    Args:
        logger: Datalogger instance
        start: Start timestamp (epoch seconds)
        end: End timestamp (epoch seconds)
        max_points: Maximum number of data points to return
        demo: Whether to use fake real-time demo generated data
        source: Optional file source (e.g. 'demo' to read from data/demo.csv)
        
    Returns:
        JSON response with downsampled data points
    """
    try:
        start = float(start)
        end = float(end)
        max_points = int(max_points)
    except Exception:
        return JSONResponse({"data": []})
        
    if source == 'demo':
        demo_path = os.path.join(logger.data_dir, "demo.csv")
        data = logger.get_range_from_file(demo_path, start, end, max_points=max_points)
    elif demo:
        data = _demo.range_query(start, end, max_points=max_points)
    else:
        data = logger.get_range(start, end, max_points=max_points)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})
