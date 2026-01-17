"""Demo API endpoint handlers.

Provides mocked data endpoints for testing without hardware.
"""

import time
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo


def register_api_demo_routes(app: FastAPI):
    """Register demo API routes with the FastAPI app."""
    app.get('/api/demo/recent')(lambda seconds=20.0, max_points=2000: api_demo_recent(seconds, max_points))
    app.get('/api/demo/range')(lambda start, end, max_points=2000: api_demo_range(start, end, max_points))
    app.get('/api/demo/highlights')(lambda start=None, end=None: api_demo_highlights(start, end))


def api_demo_recent(seconds: float = 20.0, max_points: int = 2000):
    """Get recent demo data points.
    
    Args:
        seconds: Number of seconds of recent data to retrieve
        max_points: Maximum number of data points to return
        
    Returns:
        JSON response with demo data points
    """
    pts = demo.recent(seconds=seconds, max_points=max_points)
    return JSONResponse({'points': [[ts, v] for ts, v in pts]})


def api_demo_range(start: float, end: float, max_points: int = 2000):
    """Get demo data for specified time range.
    
    Args:
        start: Start timestamp (epoch seconds)
        end: End timestamp (epoch seconds)
        max_points: Maximum number of data points to return
        
    Returns:
        JSON response with demo data points
    """
    try:
        start = float(start)
        end = float(end)
        max_points = int(max_points)
    except Exception:
        return JSONResponse({'points': []})
    pts = demo.range_query(start, end, max_points=max_points)
    return JSONResponse({'points': [[ts, v] for ts, v in pts]})


def api_demo_highlights(start: float = None, end: float = None):
    """Get demo highlights for specified time range.
    
    Args:
        start: Start timestamp (epoch seconds)
        end: End timestamp (epoch seconds)
        
    Returns:
        JSON response with demo highlights
    """
    import time
    now = time.time()
    if start is None: start = now - 3 * 3600
    if end is None: end = now
    h = demo.highlights_for_range(start, end)
    return JSONResponse(h)
