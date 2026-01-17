"""Highlights API endpoint handler.

Provides access to anomaly highlights with optional time range filtering.
"""

import json
import os
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from ... import demo as _demo


def register_api_highlights_routes(app: FastAPI, app_state, data_dir):
    """Register highlights API routes with the FastAPI app."""
    app.get("/api/highlights")(lambda start=None, end=None, demo=False: api_highlights(app_state, data_dir, start, end, demo))


def api_highlights(app_state, data_dir, start: float = None, end: float = None, demo: bool = False):
    """Get highlights, optionally filtered by time range.
    
    Args:
        app_state: FastAPI application state
        data_dir: Data directory path
        start: Optional start timestamp (epoch seconds) to filter highlights
        end: Optional end timestamp (epoch seconds) to filter highlights
        
    Returns:
        JSON response with highlights data
    """
    try:
        if demo:
            import time
            now = time.time()
            if start is None:
                start = now - 3 * 3600
            if end is None:
                end = now
            highlights = _demo.highlights_for_range(float(start), float(end))
            return JSONResponse({"highlights": highlights})

        hl = getattr(app_state, '_highlights', None)
        if hl is not None:
            highlights = hl.get_highlights()
        else:
            # fallback: try reading from disk
            path = os.path.join(data_dir, 'highlights.json')
            if os.path.exists(path):
                with open(path, 'r') as f:
                    highlights = json.load(f)
            else:
                highlights = []

        # Filter by time range if provided
        if start is not None or end is not None:
            filtered = []
            start_ts = float(start) if start is not None else None
            end_ts = float(end) if end is not None else None
            
            for h in highlights:
                # Check if highlight overlaps with the requested range
                # A highlight overlaps if: h.start_ts <= end AND h.end_ts >= start
                highlight_start = h.get('start_ts', 0)
                highlight_end = h.get('end_ts', highlight_start)
                
                if start_ts is not None and highlight_end < start_ts:
                    continue
                if end_ts is not None and highlight_start > end_ts:
                    continue
                    
                filtered.append(h)
            highlights = filtered

        return JSONResponse({"highlights": highlights})
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception("Error returning highlights")
    return JSONResponse({"highlights": []})
