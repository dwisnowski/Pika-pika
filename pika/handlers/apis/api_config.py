"""Configuration API endpoint handlers.

Provides access to current configuration and allows updating sample rate.
Uses SharedConfigBuffer for multiprocessing configuration synchronization.
"""

import json
import os
from fastapi import FastAPI, HTTPException, APIRouter
from fastapi.responses import JSONResponse
from ...shared_memory import SharedConfigBuffer

router = APIRouter()

# Global variables to hold instances passed during registration
shared_config_buffer = None
config = None
manager = None
display_fps = None
display_auto_ip = None


@router.put("/config/analysis")
async def update_analysis_config(data: dict):
    """Update analysis configuration."""
    try:
        if shared_config_buffer:
            # Get current config and update analysis section
            current_config, _ = shared_config_buffer.get_config()
            current_config['analysis_config'] = data
            shared_config_buffer.update_config(current_config)
            return {"success": True, "config": data}
        return {"success": False, "error": "Shared config buffer not available"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/config/analysis")
async def get_analysis_config():
    """Get current analysis configuration."""
    if shared_config_buffer:
        config_data, _ = shared_config_buffer.get_config()
        return config_data.get('analysis_config', {})
    return {}


@router.get("/config")
async def get_current_config():
    """Get current configuration."""
    return get_config(shared_config_buffer, config, display_fps, display_auto_ip)

@router.put("/config/sample-rate")
async def handle_update_sample_rate(data: dict):
    """Update the sample rate."""
    return update_sample_rate(shared_config_buffer, config, manager, data)


def register_api_config_routes(app: FastAPI, _shared_config_buffer, _config, _manager, _display_fps, _display_auto_ip):
    """Register configuration API routes with the FastAPI app."""
    global shared_config_buffer, config, manager, display_fps, display_auto_ip
    shared_config_buffer = _shared_config_buffer
    config = _config
    manager = _manager
    display_fps = _display_fps
    display_auto_ip = _display_auto_ip

    app.include_router(router, prefix="/api")


def get_config(shared_config_buffer, config, display_fps, display_auto_ip):
    """Get current configuration.
    
    Args:
        shared_config_buffer: SharedConfigBuffer instance
        config: Configuration dictionary (fallback)
        display_fps: Display FPS setting
        display_auto_ip: Display auto IP setting
        
    Returns:
        JSON response with current configuration
    """
    if shared_config_buffer:
        config_data, _ = shared_config_buffer.get_config()
        sample_hz = config_data.get('sample_hz', 100)
    else:
        sample_hz = config.get("sample_hz", 100)
    
    return JSONResponse({
        "sample_hz": sample_hz,
        "data_dir": config.get("data_dir", "data"),
        "port": config.get("port", 8000),
        "display_fps": display_fps,
        "display_auto_ip": display_auto_ip
    })


def update_sample_rate(shared_config_buffer, config, manager, data: dict):
    """Update the sample rate (1-860 Hz)."""
    sample_hz = data.get("sample_hz")
    if sample_hz is None:
        raise HTTPException(status_code=400, detail="sample_hz parameter is required")
    
    try:
        sample_hz = int(sample_hz)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="sample_hz must be a valid integer")
    
    if sample_hz < 1 or sample_hz > 860:
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 860 Hz")

    # Update the shared configuration buffer
    if shared_config_buffer:
        new_version = shared_config_buffer.update_sample_rate(sample_hz)
        
        # Update local config and save to file
        config["sample_hz"] = sample_hz
        config_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "config.toml")
        try:
            import tomli_w
            with open(config_path, "wb") as f:
                tomli_w.dump({"pika": config}, f)
        except ImportError:
            # If tomli_w not available, just update in memory
            pass

        # Broadcast the change to WebSocket clients
        import asyncio
        asyncio.create_task(manager.broadcast(json.dumps({
            "type": "config_update",
            "config": {"sample_hz": sample_hz},
            "version": new_version
        })))

        return JSONResponse({"success": True, "sample_hz": sample_hz, "version": new_version})
    else:
        return JSONResponse({"success": False, "message": "Shared config buffer not available"})
