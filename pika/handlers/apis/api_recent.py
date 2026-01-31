"""Recent data API endpoint handler.

Provides access to recent voltage measurements from shared memory buffer.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo as _demo
from ...shared_memory import SharedSampleBuffer


def api_recent(shared_sample_buffer, seconds: float = 5.0, demo: bool = False):
    """Get recent data points from shared memory buffer.
    
    Args:
        shared_sample_buffer: SharedSampleBuffer instance or None for demo mode
        seconds: Number of seconds of recent data to retrieve
        demo: Whether to use demo data instead of shared memory
        
    Returns:
        JSON response with recent data points
    """
    if demo:
        data = _demo.recent(seconds=seconds, max_points=2000)
    else:
        if shared_sample_buffer is None:
            # Fallback to empty data if shared memory not available
            data = []
        else:
            data = shared_sample_buffer.read_recent(seconds)
    return JSONResponse({"data": [[ts, val] for ts, val in data]})


def register_api_recent_routes(app: FastAPI, shared_sample_buffer):
    """Register recent data API routes with the FastAPI app."""
    app.get("/api/recent")(lambda seconds=5.0, demo=False: api_recent(shared_sample_buffer, seconds, demo))
