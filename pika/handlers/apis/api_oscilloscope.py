"""Oscilloscope API endpoint handlers.

Provides oscilloscope-specific configuration and control endpoints.
"""

import json
import os
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# Global variables to hold instances passed during registration
logger = None
config = None
manager = None


@router.post("/oscilloscope/mode")
async def set_oscilloscope_mode(data: dict):
    """Enable or disable oscilloscope mode (pauses/resumes CSV writing)."""
    enabled = data.get("enabled", False)
    
    if logger:
        logger.csv_write_enabled = not enabled  # Inverse: oscilloscope mode = CSV disabled
        return {
            "success": True, 
            "oscilloscope_mode": enabled,
            "csv_write_enabled": logger.csv_write_enabled
        }
    return {"success": False, "error": "Logger not available"}


@router.get("/oscilloscope/status")
async def get_oscilloscope_status():
    """Get current oscilloscope mode status."""
    if logger:
        return {
            "oscilloscope_mode": not logger.csv_write_enabled,
            "csv_write_enabled": logger.csv_write_enabled,
            "sample_hz": logger.sample_hz,
            "adc_channel": getattr(logger.adc, 'channel', 0)
        }
    return {"oscilloscope_mode": False, "csv_write_enabled": True}


@router.put("/oscilloscope/sample-rate")
async def set_oscilloscope_sample_rate(data: dict):
    """Quick sample rate update for oscilloscope mode."""
    sample_hz = data.get("sample_hz")
    if sample_hz is None or not (1 <= sample_hz <= 860):
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 860 Hz")
    
    if logger:
        logger.set_sample_rate(sample_hz)
        
        # Broadcast to WebSocket clients
        import asyncio
        if manager:
            asyncio.create_task(manager.broadcast(json.dumps({
                "type": "config_update",
                "config": {"sample_hz": sample_hz}
            })))
        
        return {"success": True, "sample_hz": logger.sample_hz}
    return {"success": False, "error": "Logger not available"}


def register_api_oscilloscope_routes(app: FastAPI, _logger, _config, _manager):
    """Register oscilloscope API routes with the FastAPI app."""
    global logger, config, manager
    logger = _logger
    config = _config
    manager = _manager

    app.include_router(router, prefix="/api")
