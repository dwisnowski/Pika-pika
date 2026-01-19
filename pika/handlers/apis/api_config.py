"""Configuration API endpoint handlers.

Provides access to current configuration and allows updating sample rate.
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
display_fps = None
display_auto_ip = None


@router.put("/config/analysis")
async def update_analysis_config(data: dict):
    """Update analysis configuration."""
    try:
        if logger:
            logger.update_analysis_config(data)
        return {"success": True, "config": (logger.analysis_config if logger else {})}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/config/analysis")
async def get_analysis_config():
    """Get current analysis configuration."""
    if logger:
        return logger.analysis_config
    return {}


def register_api_config_routes(app: FastAPI, _logger, _config, _manager, _display_fps, _display_auto_ip):
    """Register configuration API routes with the FastAPI app."""
    global logger, config, manager, display_fps, display_auto_ip
    logger = _logger
    config = _config
    manager = _manager
    display_fps = _display_fps
    display_auto_ip = _display_auto_ip

    router.get("/config")(lambda: get_config(logger, config, display_fps, display_auto_ip))
    router.put("/config/sample-rate")(lambda sample_hz: update_sample_rate(logger, config, manager, sample_hz))

    app.include_router(router, prefix="/api")


def get_config(logger, config, display_fps, display_auto_ip):
    """Get current configuration.
    
    Args:
        logger: Datalogger instance
        config: Configuration dictionary
        display_fps: Display FPS setting
        display_auto_ip: Display auto IP setting
        
    Returns:
        JSON response with current configuration
    """
    return JSONResponse({
        "sample_hz": logger.sample_hz,
        "data_dir": config.get("data_dir", "data"),
        "port": config.get("port", 8000),
        "display_fps": display_fps,
        "display_auto_ip": display_auto_ip
    })


def update_sample_rate(logger, config, manager, sample_hz: int):
    """Update the sample rate (1-100 Hz).
    
    Args:
        logger: Datalogger instance
        config: Configuration dictionary
        manager: WebSocket connection manager
        sample_hz: New sample rate in Hz
        
    Returns:
        JSON response with update result
    """
    if sample_hz < 1 or sample_hz > 100:
        raise HTTPException(status_code=400, detail="Sample rate must be between 1 and 100 Hz")

    # Update the datalogger
    if logger.set_sample_rate(sample_hz):
        # Update config and save to file
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
            "config": {"sample_hz": sample_hz}
        })))

        return JSONResponse({"success": True, "sample_hz": sample_hz})
    else:
        return JSONResponse({"success": False, "message": "No change needed"})
